"""Main OpenSprinkler module."""
import asyncio
import datetime
import functools
import hashlib
import json
import os
import threading
import urllib

import aiohttp
from backoff import expo, on_exception
from pyopensprinkler.const import (
    HARDWARE_TYPE_AC,
    HARDWARE_TYPE_DC,
    HARDWARE_TYPE_LATCHING,
    HARDWARE_VERSION_DEMO,
    HARDWARE_VERSION_LINUX,
    HARDWARE_VERSION_OSBO,
    HARDWARE_VERSION_OSPI,
    REBOOT_CAUSE_AP_RESET,
    REBOOT_CAUSE_API_REQUEST,
    REBOOT_CAUSE_CLIENT_MODE,
    REBOOT_CAUSE_FACTORY_RESET,
    REBOOT_CAUSE_FIRMWARE_UPDATE,
    REBOOT_CAUSE_NETWORK_FAILURE,
    REBOOT_CAUSE_NTP_SYNC,
    REBOOT_CAUSE_POWER_ON,
    REBOOT_CAUSE_RESET_BUTTON,
    REBOOT_CAUSE_WEATHER_FAILURE,
    SENSOR_OPTION_NORMALLY_CLOSED,
    SENSOR_OPTION_NORMALLY_OPEN,
    SENSOR_TYPE_FLOW,
    SENSOR_TYPE_NOT_CONNECTED,
    SENSOR_TYPE_PROGRAM_SWITCH,
    SENSOR_TYPE_RAIN,
    SENSOR_TYPE_SOIL,
    WEATHER_ERROR_CANT_CONNECT,
    WEATHER_ERROR_EMPTY_RESPONSE,
    WEATHER_ERROR_NOT_RECEIVED,
    WEATHER_ERROR_TIME_OUT,
)
from pyopensprinkler.program import Program
from pyopensprinkler.station import Station


def synchronized(lock):
    """ Synchronization decorator """

    def wrap(f):
        @functools.wraps(f)
        def newFunction(*args, **kw):
            with lock:
                return f(*args, **kw)

        return newFunction

    return wrap


lock = threading.Lock()


class OpenSprinklerAuthError(Exception):
    """Exception for authentication error."""


class OpenSprinklerConnectionError(Exception):
    """Exception for connection error."""


class OpenSprinklerNoStateError(Exception):
    """Exception for no state."""


class OpenSprinklerApiError(Exception):
    """Exception for an error returned by the API."""


class Controller(object):
    """OpenSprinkler Controller"""

    def __init__(self, url, password, opts=None):
        """OpenSprinkler Controller initializer."""

        if opts is None:
            opts = {}

        self._password = password
        self._md5password = hashlib.md5(password.encode("utf-8")).hexdigest()
        self._baseUrl = url.strip("/")
        self._opts = opts
        self._programs = {}
        self._stations = {}
        self._state = None
        self._last_refresh_time = None
        self._http_client = None
        self._skip_all_endpoint = os.environ.get(
            "PYOPENSPRINKLER_SKIP_ALL_ENDPOINT", None
        )
        if self._skip_all_endpoint is not None:
            self._skip_all_endpoint = self._skip_all_endpoint.lower() in [
                "true",
                "t",
                "1",
                "yes",
            ]

        if self._skip_all_endpoint is None and "skip_all_endpoint" in opts:
            self._skip_all_endpoint = opts["skip_all_endpoint"]

        self.refresh_on_update = None

        if "session" in opts:
            self._http_client = opts["session"]

        if "auto_refresh_on_update" not in opts:
            opts["auto_refresh_on_update"] = {}

        if "enabled" not in opts["auto_refresh_on_update"]:
            opts["auto_refresh_on_update"]["enabled"] = True

        if "settle_time" not in opts["auto_refresh_on_update"]:
            opts["auto_refresh_on_update"]["settle_time"] = 1

    def session_start(self):
        client = aiohttp.ClientSession()
        self._http_client = client

    async def session_close(self):
        if self._http_client is not None and "session" not in self._opts:
            await self._http_client.close()
            self._http_client = None

    async def request(self, path, params=None, raw_qs=None, refresh_on_update=None):
        if params is None:
            params = {}
        """Make a request to the API."""
        params["pw"] = self._md5password
        qs = urllib.parse.urlencode(params)
        if raw_qs is not None and len(raw_qs) > 0:
            qs = qs + "&" + raw_qs
        url = f"{self._baseUrl}{path}?{qs}"

        content = await self._request_http(url)

        refresh = self._opts["auto_refresh_on_update"]["enabled"]
        if self.refresh_on_update is not None:
            refresh = self.refresh_on_update

        if refresh_on_update is not None:
            refresh = refresh_on_update

        update_paths = ["/cv", "/co", "/cs", "/cm", "/mp", "/cp", "/dp", "/up", "/cr"]
        if refresh and path in update_paths:
            #  .1 was not enough settle time
            # .25 was mostly good but still too fast at times
            #  .5 was mostly good but still too fast at times
            # .75 was mostly good but still too fast at times
            #   1 was consistently enough time
            await asyncio.sleep(
                float(self._opts["auto_refresh_on_update"]["settle_time"])
            )
            await self.refresh()

        return content

    @synchronized(lock)
    @on_exception(expo, OpenSprinklerConnectionError, max_tries=3)
    async def _request_http(self, url):
        try:
            if self._http_client is None:
                self.session_start()

            timeout = aiohttp.ClientTimeout(total=60)
            headers = {"Accept": "*/*", "Connection": "keep-alive"}

            auth = None
            if "http_username" in self._opts:
                auth = aiohttp.BasicAuth(
                    self._opts["http_username"], self._opts["http_password"]
                )

            verify_ssl = None
            if "verify_ssl" in self._opts:
                verify_ssl = self._opts["verify_ssl"]

            async with self._http_client.get(
                url, timeout=timeout, headers=headers, verify_ssl=verify_ssl, auth=auth
            ) as resp:
                content = await resp.json(
                    encoding="UTF-8", content_type=resp.headers["Content-Type"]
                )

                if len(content) == 1:
                    if "result" in content:
                        if content["result"] == 2:
                            raise OpenSprinklerAuthError("Invalid password")
                        elif content["result"] > 2:
                            raise OpenSprinklerApiError(
                                f"Error code: {content['result']}", content["result"]
                            )
                    elif "fwv" in content:
                        raise OpenSprinklerAuthError("Invalid password")

                return content
        except aiohttp.ClientConnectionError as exc:
            raise OpenSprinklerConnectionError("Cannot connect to controller") from exc
        except ConnectionError as exc:
            raise OpenSprinklerConnectionError("Cannot connect to controller") from exc
        except json.decoder.JSONDecodeError as exc:
            raise OpenSprinklerConnectionError("Cannot connect to controller") from exc
        except KeyError as exc:
            raise OpenSprinklerAuthError("Invalid password") from exc

    async def refresh(self):
        """Refresh programs and stations"""
        await self._refresh_state()
        self._last_refresh_time = int(round(datetime.datetime.now().timestamp()))

        self._programs = {}
        for i, _ in enumerate(self._state["programs"]["pd"]):
            if i not in self._programs:
                self._programs[i] = Program(self, i)

        for i, _ in enumerate(self._state["stations"]["snames"]):
            if i not in self._stations:
                self._stations[i] = Station(self, i)

    async def _refresh_state(self):
        use_ja = True
        if self._skip_all_endpoint is not None:
            use_ja = not self._skip_all_endpoint

        if use_ja:
            try:
                content = await self.request("/ja")
                self._state = content
                return
            except OpenSprinklerApiError as exc:
                (_, err_code) = exc.args
                if err_code == 32:
                    # set for preemptive behavior on all subsequent calls
                    self._skip_all_endpoint = True
                else:
                    raise exc

        # Backwards compatibility for pre 2.1.6
        # Fallback
        settings = await self.request("/jc")
        options = await self.request("/jo")
        stations = await self.request("/jn")
        status = await self.request("/js")
        programs = await self.request("/jp")
        content = {
            "settings": settings,
            "options": options,
            "stations": stations,
            "status": status,
            "programs": programs,
        }

        self._state = content

    def _retrieve_state(self):
        if self._state is None:
            raise OpenSprinklerNoStateError("No state. Please refresh")
        return self._state

    def _get_option(self, option):
        """Retrieve option"""
        try:
            return self._get_options()[option]
        except KeyError:
            return None

    def _get_options(self):
        """Retrieve options"""
        return self._retrieve_state()["options"]

    async def _set_option(self, option, value):
        """Set option"""
        params = {option: value}
        content = await self.request("/co", params)
        return content["result"]

    def _get_variable(self, option):
        """Retrieve variable"""
        try:
            return self._get_variables()[option]
        except KeyError:
            return None

    def _get_variables(self):
        """Retrieve variables"""
        return self._retrieve_state()["settings"]

    async def _set_variable(self, variable, value):
        """Set variable"""
        params = {variable: value}
        content = await self.request("/cv", params)
        return content["result"]

    def _sensor_type_to_name(self, sensor_type):
        """Get sensor type name from value"""
        if sensor_type == 0:
            return SENSOR_TYPE_NOT_CONNECTED

        if sensor_type == 1:
            return SENSOR_TYPE_RAIN

        if sensor_type == 2:
            return SENSOR_TYPE_FLOW

        if sensor_type == 3:
            return SENSOR_TYPE_SOIL

        if sensor_type == 240:
            return SENSOR_TYPE_PROGRAM_SWITCH

        raise ValueError("unknown sensor_type value")

    def _sensor_type_enabled(self, sensor_type):
        """Retrieve if any sensor of given type enabled"""
        return bool(
            self.sensor_1_type == sensor_type or self.sensor_2_type == sensor_type
        )

    def _sensor_option_to_name(self, sensor_option):
        """Get sensor option name from value"""
        if sensor_option == 0:
            return SENSOR_OPTION_NORMALLY_CLOSED

        if sensor_option == 1:
            return SENSOR_OPTION_NORMALLY_OPEN

        raise ValueError("unknown sensor_option value")

    def _ip_from_options(self, option_name_prefix):
        """Convert 4 datapoint IP addresses into string"""
        ip = ""
        for i in [1, 2, 3, 4]:
            option = option_name_prefix + str(i)
            octet = self._get_option(option)
            if octet is None or len(str(octet)) < 1:
                return None

            ip = ip + str(octet)
            if i < 4:
                ip = ip + "."

        return ip

    def _timestamp_to_utc(self, timestamp):
        if timestamp is None:
            return None
        offset = (self._get_option("tz") - 48) * 15 * 60
        return timestamp if timestamp == 0 else timestamp - offset

    # controller variables
    async def enable(self):
        """Enable operation"""
        return await self._set_variable("en", 1)

    async def disable(self):
        """Disable operation"""
        return await self._set_variable("en", 0)

    async def reboot(self):
        return await self._set_variable("rbt", 1)

    async def set_rain_delay(self, hours):
        """
        Set rain delay time (in hours). Range is 0 to 32767. A value of 0 turns off rain delay.
        """

        if hours < 0 or hours > 32767:
            raise ValueError("level must be 0-32767")

        return await self._set_variable("rd", hours)

    async def disable_rain_delay(self):
        return await self._set_variable("rd", 0)

    async def enable_remote_extension_mode(self):
        return await self._set_variable("re", 1)

    async def disable_remote_extension_mode(self):
        return await self._set_variable("re", 0)

    async def stop_all_stations(self):
        """Stop all running and waiting stations"""
        return await self._set_variable("rsn", 1)

    async def firmware_update(self):
        return await self._set_variable("update", 1)

    # controller options
    async def set_water_level(self, level):
        """
        Water level (i.e. % Watering). Acceptable range is 0 to 250.
        """

        if level < 0 or level > 250:
            raise ValueError("level must be 0-250")

        return await self._set_option("wl", level)

    async def run_once_program(self, station_times):
        """Run once program"""
        params = {"t": station_times}

        t = json.dumps(params.pop("t", None)).replace(" ", "")
        t = t.strip()

        content = await self.request("/cr", None, f"t={t}")
        return content["result"]

    async def set_password(self, password):
        """Set password"""
        md5password = hashlib.md5(password.encode("utf-8")).hexdigest()
        params = {"pw": self._md5password, "npw": md5password, "cpw": md5password}

        content = await self.request("/sp", params)
        self._md5password = md5password
        return content["result"]

    async def create_program(self, name):
        """Create new disabled program with first station running for 1 minute on Monday midnight"""
        params = {"pid": -1, "name": name, "v": "[0,1,0,[0,0,0,0],[60,0,0,0,0,0,0,0]]"}

        content = await self.request("/cp", params)
        return content["result"]

    async def delete_program(self, index):
        """Delete program"""
        content = await self.request("/dp", {"pid": index})
        return content["result"]

    @property
    def last_refresh_time(self):
        """Retrieve last refresh time"""
        return self._last_refresh_time

    @property
    def enabled(self):
        """Retrieve operation enabled"""
        return bool(self._get_variable("en"))

    @property
    def mac_address(self):
        """Retrieve controller mac address"""
        return self._get_variable("mac")

    @property
    def firmware_version(self):
        """Retrieve firmware version"""
        return self._get_option("fwv")

    @property
    def firmware_version_name(self):
        """Retrieve firmware version name"""
        fwv = self.firmware_version
        try:
            return f"{ int( fwv / 100 )}.{ int( fwv / 10 ) % 10 }.{ fwv % 10 }"
        except TypeError:
            return None

    @property
    def firmware_minor_version(self):
        """Retrieve firmware minor version"""
        return self._get_option("fwm")

    @property
    def hardware_version(self):
        """Retrieve hardware version"""
        return self._get_option("hwv")

    @property
    def hardware_version_name(self):
        """Retrieve hardware version name"""
        if self.hardware_version == HARDWARE_VERSION_OSPI:
            return "OSPi"

        if self.hardware_version == HARDWARE_VERSION_OSBO:
            return "OSBo"

        if self.hardware_version == HARDWARE_VERSION_LINUX:
            return "Linux"

        if self.hardware_version == HARDWARE_VERSION_DEMO:
            return "Demo"

        try:
            return f"{ int( self.hardware_version / 10 ) % 10 }.{ self.hardware_version % 10 }"
        except TypeError:
            return None

    @property
    def hardware_type(self):
        """Retrieve hardware type"""
        return self._get_option("hwt")

    @property
    def hardware_type_name(self):
        """Retrieve hardware type name"""
        if self.hardware_type == HARDWARE_TYPE_AC:
            return "AC"

        if self.hardware_type == HARDWARE_TYPE_DC:
            return "DC"

        if self.hardware_type == HARDWARE_TYPE_LATCHING:
            return "Latching"

        return None

    @property
    def device_id(self):
        """Retrieve device ID"""
        return self._get_option("devid")

    @property
    def device_time(self):
        """Retrieve device time"""
        return self._timestamp_to_utc(self._get_variable("devt"))

    @property
    def ignore_password_enabled(self):
        """Retrieve ignore password"""
        return bool(self._get_option("ipas"))

    @property
    def special_station_auto_refresh_enabled(self):
        """Retrieve special station auto refresh"""
        return bool(self._get_option("sar"))

    @property
    def detected_expansion_board_count(self):
        """Retrieve number of detected expansion boards"""
        return self._get_option("dexp")

    @property
    def maximum_expansion_board_count(self):
        """Retrieve maximum number of expansion boards"""
        return self._get_option("mexp")

    @property
    def dhcp_enabled(self):
        """Retrieve dhcp enabled"""
        return bool(self._get_option("dhcp"))

    @property
    def ip_address(self):
        """Retrieve controller IP address"""
        return self._ip_from_options("ip")

    @property
    def gateway_address(self):
        """Retrieve controller gateway IP address"""
        return self._ip_from_options("gw")

    @property
    def dns_address(self):
        """Retrieve controller DNS IP address"""
        return self._ip_from_options("dns")

    @property
    def ip_subnet(self):
        """Retrieve controller IP subnet"""
        return self._ip_from_options("subn")

    @property
    def ntp_address(self):
        """Retrieve controller NTP IP address"""
        return self._ip_from_options("ntp")

    @property
    def ntp_enabled(self):
        """Retrieve NTP enabled"""
        return bool(self._get_option("ntp"))

    # lrun [station index, program index, duration, end time]
    @property
    def last_run_station(self):
        """Retrieve last run station"""
        return self._get_variable("lrun")[0]

    @property
    def last_run_program(self):
        """Retrieve last run program"""
        return self._get_variable("lrun")[1]

    @property
    def last_run_duration(self):
        """Retrieve last run duration"""
        return self._get_variable("lrun")[2]

    @property
    def last_run_end_time(self):
        """Retrieve last run end time"""
        return self._timestamp_to_utc(self._get_variable("lrun")[3])

    @property
    def rssi(self):
        """Retrieve RSSI"""
        return self._get_variable("RSSI")

    @property
    def latitude(self):
        """Retrieve latitude"""
        loc = self._get_variable("loc")
        if len(loc) < 1 or "," not in loc:
            return None

        return float(loc.split(",")[0].strip())

    @property
    def longitude(self):
        """Retrieve longitude"""
        loc = self._get_variable("loc")
        if len(loc) < 1 or "," not in loc:
            return None

        return float(loc.split(",")[1].strip())

    @property
    def current_draw(self):
        """Retrieve current draw in mA"""
        return self._get_variable("curr")

    @property
    def master_station_1(self):
        """
        Retrieve master station 1

        Note this value is 1 indexed, 0 means disabled
        """
        return self._get_option("mas")

    @property
    def master_station_1_time_on_adjustment(self):
        """
        Master 1 and 2 on adjusted time (in steps of 5 seconds). Acceptable range is 0 to 600 (note: positive).
        """
        return self._get_option("mton")

    @property
    def master_station_1_time_off_adjustment(self):
        """
        Master 1 and 2 off adjusted time (in steps of 5 seconds). Acceptable range is -600 to 0 (note: negative).
        """
        return self._get_option("mtof")

    @property
    def master_station_2(self):
        """
        Retrieve master station 2

        Note this value is 1 indexed, 0 means disabled
        """
        return self._get_option("mas2")

    @property
    def master_station_2_time_on_adjustment(self):
        """
        Master 1 and 2 on adjusted time (in steps of 5 seconds). Acceptable range is 0 to 600 (note: positive).
        """
        return self._get_option("mton2")

    @property
    def master_station_2_time_off_adjustment(self):
        """
        Master 1 and 2 off adjusted time (in steps of 5 seconds). Acceptable range is -600 to 0 (note: negative).
        """
        return self._get_option("mtof2")

    @property
    def rain_delay_active(self):
        """Retrieve rain delay active"""
        return bool(self._get_variable("rd"))

    @property
    def rain_delay_stop_time(self):
        """Retrieve rain delay stop time"""
        return self._get_variable("rdst")

    @property
    def rain_sensor_active(self):
        """Retrieve rain sensor active"""
        try:
            return bool(self._get_variable("rs"))
        except KeyError:
            return None

    @property
    def sensor_1_active(self):
        """Retrieve sensor 1 active"""
        if self._get_variable("sn1") is not None:
            return bool(self._get_variable("sn1"))

        if self._get_variable("rs") is not None:
            return bool(self._get_variable("rs"))

        return None

    @property
    def sensor_1_enabled(self):
        """Retrieve sensor 1 enabled"""
        if self.sensor_1_type is None:
            return None

        return bool(self.sensor_1_type > 0)

    @property
    def sensor_1_type(self):
        """Retrieve sensor 1 type"""
        if self._get_option("sn1t") is not None:
            return self._get_option("sn1t")

        return self._get_option("urs")

    @property
    def sensor_1_type_name(self):
        """Retrieve sensor 1 type name"""
        if self.sensor_1_type is None:
            return None

        return self._sensor_type_to_name(self.sensor_1_type)

    @property
    def sensor_1_option(self):
        """Retrieve sensor 1 option"""
        if self._get_option("sn1o") is not None:
            return self._get_option("sn1o")

        return self._get_option("rso")

    @property
    def sensor_1_option_name(self):
        """Retrieve sensor 1 option name"""
        if self.sensor_1_option is None:
            return None

        return self._sensor_option_to_name(self.sensor_1_option)

    @property
    def sensor_1_delayed_on_time(self):
        """
        Retrieve sensor 1 delayed on time

        Delayed on time and delayed off time (unit is minutes).
        """
        return self._get_option("sn1on")

    @property
    def sensor_1_delayed_off_time(self):
        """
        Retrieve sensor 1 delayed off time

        Delayed on time and delayed off time (unit is minutes).
        """
        return self._get_option("sn1of")

    @property
    def sensor_2_active(self):
        """Retrieve sensor 2 active"""
        if self.sensor_2_type is None:
            return None

        return bool(self._get_variable("sn2"))

    @property
    def sensor_2_enabled(self):
        """Retrieve sensor 2 enabled"""
        if self.sensor_2_type is None:
            return None

        return bool(self.sensor_2_type > 0)

    @property
    def sensor_2_type(self):
        """Retrieve sensor 2 type"""
        return self._get_option("sn2t")

    @property
    def sensor_2_type_name(self):
        """Retrieve sensor 2 type name"""
        if self.sensor_2_type is None:
            return None

        return self._sensor_type_to_name(self.sensor_2_type)

    @property
    def sensor_2_option(self):
        """Retrieve sensor 2 option"""
        return self._get_option("sn2o")

    @property
    def sensor_2_option_name(self):
        """Retrieve sensor 2 option name"""
        if self.sensor_2_option is None:
            return None

        return self._sensor_option_to_name(self.sensor_2_option)

    @property
    def sensor_2_delayed_on_time(self):
        """
        Retrieve sensor 2 delayed on time

        Delayed on time and delayed off time (unit is minutes).
        """
        return self._get_option("sn2on")

    @property
    def sensor_2_delayed_off_time(self):
        """
        Retrieve sensor 1 delayed off time

        Delayed on time and delayed off time (unit is minutes).
        """
        return self._get_option("sn2of")

    @property
    def water_level(self):
        """Retrieve water level"""
        return self._get_option("wl")

    @property
    def rain_sensor_enabled(self):
        """Retrieve rain sensor enabled"""
        return self._sensor_type_enabled(1)

    @property
    def flow_sensor_enabled(self):
        """Retrieve flow sensor enabled"""
        return self._sensor_type_enabled(2)

    @property
    def soil_sensor_enabled(self):
        """Retrieve soil sensor enabled"""
        return self._sensor_type_enabled(3)

    @property
    def program_switch_sensor_enabled(self):
        """Retrieve program switch sensor enabled"""
        return self._sensor_type_enabled(240)

    @property
    def flow_rate(self):
        """Return flow rate"""
        if not self.flow_sensor_enabled:
            return None

        fpr0 = self._get_option("fpr0")
        fpr1 = self._get_option("fpr1")
        flwrt = self._get_variable("flwrt")
        flcrt = self._get_variable("flcrt")

        try:
            return (flcrt * ((fpr1 << 8) + fpr0) / 100) / (flwrt / 60)
        except (TypeError, ZeroDivisionError):
            return None

    @property
    def flow_count_window(self):
        """Retrieve flow count window in seconds"""
        return self._get_variable("flwrt")

    @property
    def flow_count(self):
        """Retrieve flow count"""
        return self._get_variable("flcrt")

    @property
    def last_weather_call(self):
        """Retrieve last weather call"""
        return self._timestamp_to_utc(self._get_variable("lwc"))

    @property
    def last_successfull_weather_call(self):
        """Retrieve last successfull weather call"""
        return self._timestamp_to_utc(self._get_variable("lswc"))

    @property
    def last_weather_call_error(self):
        """Retrieve last weather call error"""
        return self._get_variable("wterr")

    @property
    def last_weather_call_error_name(self):
        """Retrieve last weather call error name"""
        if self.last_weather_call_error == -1:
            return WEATHER_ERROR_NOT_RECEIVED

        if self.last_weather_call_error == -2:
            return WEATHER_ERROR_CANT_CONNECT

        if self.last_weather_call_error == -3:
            return WEATHER_ERROR_TIME_OUT

        if self.last_weather_call_error == -4:
            return WEATHER_ERROR_EMPTY_RESPONSE

    @property
    def sunrise(self):
        """
        Retrieve sunrise

        Today’s sunrise time (number of minutes from midnight).
        """
        return self._get_variable("sunrise")

    @property
    def sunset(self):
        """
        Retrieve sunset

        Today’s sunset time (number of minutes from midnight).
        """
        return self._get_variable("sunset")

    @property
    def last_reboot_time(self):
        """Retrieve last device reboot time"""
        return self._timestamp_to_utc(self._get_variable("lupt"))

    @property
    def last_reboot_cause(self):
        """Retrieve last device reboot cause"""
        return self._get_variable("lrbtc")

    @property
    def last_reboot_cause_name(self):
        """Retrieve last device reboot cause name"""
        if self.last_reboot_cause == 0:
            return None

        if self.last_reboot_cause == 1:
            return REBOOT_CAUSE_FACTORY_RESET

        if self.last_reboot_cause == 2:
            return REBOOT_CAUSE_RESET_BUTTON

        if self.last_reboot_cause == 3:
            return REBOOT_CAUSE_AP_RESET

        if self.last_reboot_cause == 4:
            return REBOOT_CAUSE_API_REQUEST

        if self.last_reboot_cause == 5:
            return REBOOT_CAUSE_API_REQUEST

        if self.last_reboot_cause == 6:
            return REBOOT_CAUSE_CLIENT_MODE

        if self.last_reboot_cause == 7:
            return REBOOT_CAUSE_FIRMWARE_UPDATE

        if self.last_reboot_cause == 8:
            return REBOOT_CAUSE_WEATHER_FAILURE

        if self.last_reboot_cause == 9:
            return REBOOT_CAUSE_NETWORK_FAILURE

        if self.last_reboot_cause == 10:
            return REBOOT_CAUSE_NTP_SYNC

        if self.last_reboot_cause == 99:
            return REBOOT_CAUSE_POWER_ON

    @property
    def mqtt_settings(self):
        """Retrieve MQTT settings"""
        return self._get_variable("mqtt")

    @property
    def mqtt_enabled(self):
        """Return if MQTT is enabled"""
        return (
            bool(self.mqtt_settings["en"]) if self.mqtt_settings is not None else None
        )

    @property
    def programs(self):
        """Return programs"""
        return self._programs

    @property
    def stations(self):
        """Return stations"""
        return self._stations
