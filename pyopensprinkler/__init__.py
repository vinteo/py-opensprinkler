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

from .exceptions import (
    OpenSprinklerApiError,
    OpenSprinklerAuthError,
    OpenSprinklerConnectionError,
    OpenSprinklerNoStateError,
)


def synchronized(lock):
    """Synchronization decorator"""

    def wrap(f):
        @functools.wraps(f)
        def newFunction(*args, **kw):
            with lock:
                return f(*args, **kw)

        return newFunction

    return wrap


lock = threading.Lock()


class Controller(object):
    """OpenSprinkler Controller"""

    def __init__(self, url, password, opts=None):
        """OpenSprinkler Controller initializer.

        Args:
            url: Controller URL in the form ``http[s]://hostname[:port]``.
            password: Controller password (plaintext; MD5-hashed for API calls).
            opts: Optional dict of connection and behavior options:

                - ``session``: externally managed ``aiohttp.ClientSession`` to
                  reuse; the caller is responsible for closing it.
                - ``skip_all_endpoint``: if True, never use the ``/ja``
                  all-in-one endpoint and always use the per-section
                  endpoints. Overridden by the
                  ``PYOPENSPRINKLER_SKIP_ALL_ENDPOINT`` environment variable.
                - ``auto_refresh_on_update``: dict with ``enabled`` (bool,
                  default True) and ``settle_time`` (seconds, default 1)
                  controlling the automatic state refresh after update calls.
                - ``http_username`` / ``http_password``: HTTP basic auth
                  credentials when the controller sits behind an
                  authenticating proxy.
                - ``verify_ssl``: SSL verification flag passed to aiohttp.
        """

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
        """Create a new internally managed aiohttp client session."""
        client = aiohttp.ClientSession()
        self._http_client = client

    async def session_close(self):
        """Close the internally managed aiohttp client session.

        Does nothing when an external session was provided via the
        ``session`` option or when no session has been started.
        """
        if self._http_client is not None and "session" not in self._opts:
            await self._http_client.close()
            self._http_client = None

    async def request(self, path, params=None, raw_qs=None, refresh_on_update=None):
        """Make a request to the API.

        Args:
            path: API endpoint path, e.g. ``/jc``.
            params: Optional dict of query string parameters.
            raw_qs: Optional pre-encoded query string appended verbatim
                after ``params``.
            refresh_on_update: Override the auto-refresh behavior for this
                call; None defers to the instance configuration.

        Returns:
            Decoded JSON response as a dict.

        Raises:
            OpenSprinklerAuthError: If the password is rejected.
            OpenSprinklerApiError: If the API returns an error result code.
            OpenSprinklerConnectionError: If the controller is unreachable.
        """
        if params is None:
            params = {}
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

        update_paths = [
            "/cv",
            "/co",
            "/cs",
            "/cm",
            "/mp",
            "/cp",
            "/dp",
            "/up",
            "/cr",
            "/pq",
        ]
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
        """Perform the HTTP GET with retries and error mapping."""
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

            self._http_client.cookie_jar.clear()

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
        """Refresh programs and stations.

        Fetches the full controller state and rebuilds the ``programs``
        and ``stations`` dicts. Must be called at least once before
        reading any state-dependent properties.
        """
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

    async def _set_pause(self, value):
        """Set pause"""
        variable = "dur"
        params = {variable: value}
        content = await self.request("/pq", params)
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
        """Enable controller operation.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("en", 1)

    async def disable(self):
        """Disable controller operation.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("en", 0)

    async def reboot(self):
        """Reboot the controller.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("rbt", 1)

    async def set_rain_delay(self, hours):
        """Set rain delay time.

        Args:
            hours: Rain delay in hours, 0-32767. A value of 0 turns off
                rain delay.

        Returns:
            API result code (1 = success).

        Raises:
            ValueError: If hours is outside 0-32767.
        """

        if hours < 0 or hours > 32767:
            raise ValueError("level must be 0-32767")

        return await self._set_variable("rd", hours)

    async def disable_rain_delay(self):
        """Turn off rain delay.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("rd", 0)

    async def set_station_delay(self, seconds):
        """Set station delay time.

        Args:
            seconds: Station delay in seconds, -600 to 600 in increments
                of 5.

        Returns:
            API result code (1 = success).

        Raises:
            ValueError: If seconds is outside -600 to 600 or not a
                multiple of 5.
        """

        if (not -600 <= seconds <= 600) or (seconds % 5 != 0):
            raise ValueError(
                "Delay must be in seconds between -600 to 600 in increments of 5 seconds"
            )
        return await self._set_option("sdt", seconds)

    async def set_pause(self, seconds):
        """Pause operation of running stations.

        Args:
            seconds: Pause duration in seconds, 0-86400 (24 hours). A
                value of 0 cancels any current pause.

        Returns:
            API result code (1 = success).

        Raises:
            ValueError: If seconds is outside 0-86400.
        """
        # Note that the API does not actually specify a limit, but the UI footer cannot properly
        # represent values above 24 hours so we constrain it to avoid misleading the user.
        if seconds < 0 or seconds > 86400:
            raise ValueError("pause must be 0 - 86400")

        return await self._set_pause(seconds)

    async def disable_pause(self):
        """Cancel any current pause.

        Returns:
            API result code (1 = success).
        """
        return await self._set_pause(0)

    async def enable_remote_extension_mode(self):
        """Enable remote extension mode.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("re", 1)

    async def disable_remote_extension_mode(self):
        """Disable remote extension mode.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("re", 0)

    async def stop_all_stations(self):
        """Stop all running and waiting stations.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("rsn", 1)

    async def firmware_update(self):
        """Trigger a firmware update.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("update", 1)

    # controller options
    async def set_water_level(self, level):
        """Set water level (i.e. % Watering).

        Requires firmware 2.1.9 or newer.

        Args:
            level: Water level percentage, 0-250.

        Returns:
            API result code (1 = success).

        Raises:
            ValueError: If level is outside 0-250.
        """

        if level < 0 or level > 250:
            raise ValueError("level must be 0-250")

        return await self._set_option("wl", level)

    async def run_once_program(self, station_times, uwt=None, qo=None):
        """Run a once-off program with the given per-station durations.

        Args:
            station_times: List of run durations in seconds, one entry per
                station (0 to skip a station).
            uwt: Optional weather adjustment flag (0/1); when 1 the
                current water level is applied to the durations.
            qo: Optional queue option; when set the run is queued rather
                than interrupting running stations.

        Returns:
            API result code (1 = success).
        """
        t = json.dumps(station_times).replace(" ", "").strip()
        params = {}
        if uwt is not None:
            params["uwt"] = uwt
        if qo is not None:
            params["qo"] = qo
        content = await self.request("/cr", params, f"t={t}")
        return content["result"]

    async def set_password(self, password):
        """Set the controller password.

        Args:
            password: New plaintext password; stored and used as its MD5
                hash for subsequent API calls.

        Returns:
            API result code (1 = success).
        """
        md5password = hashlib.md5(password.encode("utf-8")).hexdigest()
        params = {"pw": self._md5password, "npw": md5password, "cpw": md5password}

        content = await self.request("/sp", params)
        self._md5password = md5password
        return content["result"]

    async def create_program(self, name):
        """Create a new program.

        The program is created disabled, with the first station running
        for 1 minute on Monday at midnight.

        Args:
            name: Name of the new program.

        Returns:
            API result code (1 = success).
        """
        params = {"pid": -1, "name": name, "v": "[0,1,0,[0,0,0,0],[60,0,0,0,0,0,0,0]]"}

        content = await self.request("/cp", params)
        return content["result"]

    async def delete_program(self, index):
        """Delete a program.

        Args:
            index: 0-based index of the program to delete.

        Returns:
            API result code (1 = success).
        """
        content = await self.request("/dp", {"pid": index})
        return content["result"]

    @property
    def last_refresh_time(self):
        """Epoch timestamp of the last successful refresh, or None."""
        return self._last_refresh_time

    @property
    def enabled(self):
        """Whether controller operation is enabled."""
        return bool(self._get_variable("en"))

    @property
    def mac_address(self):
        """Controller MAC address."""
        return self._get_variable("mac")

    @property
    def firmware_version(self):
        """Firmware version as an integer, e.g. 219 for 2.1.9."""
        return self._get_option("fwv")

    @property
    def firmware_version_name(self):
        """Firmware version as a string, e.g. '2.1.9', or None."""
        fwv = self.firmware_version
        try:
            return f"{int(fwv / 100)}.{int(fwv / 10) % 10}.{fwv % 10}"
        except TypeError:
            return None

    @property
    def firmware_minor_version(self):
        """Firmware minor version (the number in parentheses), or None."""
        return self._get_option("fwm")

    @property
    def hardware_version(self):
        """Hardware version as an integer, or None."""
        return self._get_option("hwv")

    @property
    def hardware_version_name(self):
        """Hardware version name, e.g. 'OSPi', 'OSBo', 'Linux', 'Demo',
        or a 'major.minor' string."""
        if self.hardware_version == HARDWARE_VERSION_OSPI:
            return "OSPi"

        if self.hardware_version == HARDWARE_VERSION_OSBO:
            return "OSBo"

        if self.hardware_version == HARDWARE_VERSION_LINUX:
            return "Linux"

        if self.hardware_version == HARDWARE_VERSION_DEMO:
            return "Demo"

        try:
            return (
                f"{int(self.hardware_version / 10) % 10}.{self.hardware_version % 10}"
            )
        except TypeError:
            return None

    @property
    def hardware_type(self):
        """Hardware type integer (0 = AC, 1 = DC, 2 = Latching)."""
        return self._get_option("hwt")

    @property
    def hardware_type_name(self):
        """Hardware type name ('AC', 'DC', or 'Latching'), or None."""
        if self.hardware_type == HARDWARE_TYPE_AC:
            return "AC"

        if self.hardware_type == HARDWARE_TYPE_DC:
            return "DC"

        if self.hardware_type == HARDWARE_TYPE_LATCHING:
            return "Latching"

        return None

    @property
    def device_id(self):
        """Device ID."""
        return self._get_option("devid")

    @property
    def device_time(self):
        """Controller device time as a UTC epoch timestamp."""
        return self._timestamp_to_utc(self._get_variable("devt"))

    @property
    def ignore_password_enabled(self):
        """Whether the ignore password option is enabled."""
        return bool(self._get_option("ipas"))

    @property
    def special_station_auto_refresh_enabled(self):
        """Whether special station auto refresh is enabled."""
        return bool(self._get_option("sar"))

    @property
    def detected_expansion_board_count(self):
        """Number of detected expansion boards."""
        return self._get_option("dexp")

    @property
    def maximum_expansion_board_count(self):
        """Maximum number of supported expansion boards."""
        return self._get_option("mexp")

    @property
    def dhcp_enabled(self):
        """Whether DHCP is enabled."""
        return bool(self._get_option("dhcp"))

    @property
    def ip_address(self):
        """Controller IP address, or None if not set."""
        return self._ip_from_options("ip")

    @property
    def gateway_address(self):
        """Controller gateway IP address, or None if not set."""
        return self._ip_from_options("gw")

    @property
    def dns_address(self):
        """Controller DNS IP address, or None if not set."""
        return self._ip_from_options("dns")

    @property
    def ip_subnet(self):
        """Controller IP subnet, or None if not set."""
        return self._ip_from_options("subn")

    @property
    def ntp_address(self):
        """Controller NTP IP address, or None if not set."""
        return self._ip_from_options("ntp")

    @property
    def ntp_enabled(self):
        """Whether NTP is enabled."""
        return bool(self._get_option("ntp"))

    # lrun [station index, program index, duration, end time]
    @property
    def last_run_station(self):
        """Station index of the last station run."""
        return self._get_variable("lrun")[0]

    @property
    def last_run_program(self):
        """Program index of the last station run (0 for manual runs)."""
        return self._get_variable("lrun")[1]

    @property
    def last_run_duration(self):
        """Duration of the last station run in seconds."""
        return self._get_variable("lrun")[2]

    @property
    def last_run_end_time(self):
        """End time of the last station run as a UTC epoch timestamp."""
        return self._timestamp_to_utc(self._get_variable("lrun")[3])

    @property
    def rssi(self):
        """WiFi signal strength (RSSI), or None if not reported."""
        return self._get_variable("RSSI")

    @property
    def latitude(self):
        """Configured latitude, or None if location is not set."""
        loc = self._get_variable("loc")
        if len(loc) < 1 or "," not in loc:
            return None

        return float(loc.split(",")[0].strip())

    @property
    def longitude(self):
        """Configured longitude, or None if location is not set."""
        loc = self._get_variable("loc")
        if len(loc) < 1 or "," not in loc:
            return None

        return float(loc.split(",")[1].strip())

    @property
    def current_draw(self):
        """Current draw in mA."""
        return self._get_variable("curr")

    @property
    def station_delay(self):
        """Station delay in seconds."""
        return self._get_option("sdt")

    @property
    def master_station_1(self):
        """Master station 1 index (1-based; 0 means disabled)."""
        return self._get_option("mas")

    @property
    def master_station_1_time_on_adjustment(self):
        """Master 1 on adjustment time (steps of 5 seconds, 0 to 600)."""
        return self._get_option("mton")

    @property
    def master_station_1_time_off_adjustment(self):
        """Master 1 off adjustment time (steps of 5 seconds, -600 to 0)."""
        return self._get_option("mtof")

    @property
    def master_station_2(self):
        """Master station 2 index (1-based; 0 means disabled)."""
        return self._get_option("mas2")

    @property
    def master_station_2_time_on_adjustment(self):
        """Master 2 on adjustment time (steps of 5 seconds, 0 to 600)."""
        return self._get_option("mton2")

    @property
    def master_station_2_time_off_adjustment(self):
        """Master 2 off adjustment time (steps of 5 seconds, -600 to 0)."""
        return self._get_option("mtof2")

    @property
    def pause_active(self):
        """Whether a pause is currently active."""
        return bool(self._get_variable("pq"))

    @property
    def pause_time_remaining(self):
        """Remaining pause time in seconds."""
        return self._get_variable("pt")

    @property
    def rain_delay_active(self):
        """Whether a rain delay is currently active."""
        return bool(self._get_variable("rd"))

    @property
    def rain_delay_stop_time(self):
        """Rain delay stop time as a UTC epoch timestamp."""
        return self._timestamp_to_utc(self._get_variable("rdst"))

    @property
    def rain_sensor_active(self):
        """Whether the rain sensor is active, or None if not reported."""
        try:
            return bool(self._get_variable("rs"))
        except KeyError:
            return None

    @property
    def sensor_1_active(self):
        """Whether sensor 1 is active, or None if not reported."""
        if self._get_variable("sn1") is not None:
            return bool(self._get_variable("sn1"))

        if self._get_variable("rs") is not None:
            return bool(self._get_variable("rs"))

        return None

    @property
    def sensor_1_enabled(self):
        """Whether sensor 1 is enabled, or None if no type is configured."""
        if self.sensor_1_type is None:
            return None

        return bool(self.sensor_1_type > 0)

    @property
    def sensor_1_type(self):
        """Sensor 1 type integer, or None if not reported."""
        if self._get_option("sn1t") is not None:
            return self._get_option("sn1t")

        return self._get_option("urs")

    @property
    def sensor_1_type_name(self):
        """Sensor 1 type name (e.g. 'rain', 'flow'), or None."""
        if self.sensor_1_type is None:
            return None

        return self._sensor_type_to_name(self.sensor_1_type)

    @property
    def sensor_1_option(self):
        """Sensor 1 option integer (0 = normally closed, 1 = normally
        open), or None if not reported."""
        if self._get_option("sn1o") is not None:
            return self._get_option("sn1o")

        return self._get_option("rso")

    @property
    def sensor_1_option_name(self):
        """Sensor 1 option name ('normally_closed' or 'normally_open'),
        or None."""
        if self.sensor_1_option is None:
            return None

        return self._sensor_option_to_name(self.sensor_1_option)

    @property
    def sensor_1_delayed_on_time(self):
        """Sensor 1 delayed on time in minutes."""
        return self._get_option("sn1on")

    @property
    def sensor_1_delayed_off_time(self):
        """Sensor 1 delayed off time in minutes."""
        return self._get_option("sn1of")

    @property
    def sensor_2_active(self):
        """Whether sensor 2 is active, or None if not reported."""
        if self.sensor_2_type is None:
            return None

        return bool(self._get_variable("sn2"))

    @property
    def sensor_2_enabled(self):
        """Whether sensor 2 is enabled, or None if no type is configured."""
        if self.sensor_2_type is None:
            return None

        return bool(self.sensor_2_type > 0)

    @property
    def sensor_2_type(self):
        """Sensor 2 type integer, or None if not reported."""
        return self._get_option("sn2t")

    @property
    def sensor_2_type_name(self):
        """Sensor 2 type name (e.g. 'rain', 'flow'), or None."""
        if self.sensor_2_type is None:
            return None

        return self._sensor_type_to_name(self.sensor_2_type)

    @property
    def sensor_2_option(self):
        """Sensor 2 option integer (0 = normally closed, 1 = normally
        open), or None if not reported."""
        return self._get_option("sn2o")

    @property
    def sensor_2_option_name(self):
        """Sensor 2 option name ('normally_closed' or 'normally_open'),
        or None."""
        if self.sensor_2_option is None:
            return None

        return self._sensor_option_to_name(self.sensor_2_option)

    @property
    def sensor_2_delayed_on_time(self):
        """Sensor 2 delayed on time in minutes."""
        return self._get_option("sn2on")

    @property
    def sensor_2_delayed_off_time(self):
        """Sensor 2 delayed off time in minutes."""
        return self._get_option("sn2of")

    @property
    def water_level(self):
        """Water level (% Watering), 0-250."""
        return self._get_option("wl")

    @property
    def rain_sensor_enabled(self):
        """Whether a rain sensor is enabled on either sensor input."""
        return self._sensor_type_enabled(1)

    @property
    def flow_sensor_enabled(self):
        """Whether a flow sensor is enabled on either sensor input."""
        return self._sensor_type_enabled(2)

    @property
    def soil_sensor_enabled(self):
        """Whether a soil sensor is enabled on either sensor input."""
        return self._sensor_type_enabled(3)

    @property
    def program_switch_sensor_enabled(self):
        """Whether a program switch sensor is enabled on either input."""
        return self._sensor_type_enabled(240)

    @property
    def flow_rate(self):
        """Computed flow rate, or None when no flow sensor is enabled or
        the reading is unavailable."""
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
        """Flow count window in seconds."""
        return self._get_variable("flwrt")

    @property
    def flow_count(self):
        """Flow pulse count within the flow count window."""
        return self._get_variable("flcrt")

    @property
    def last_weather_call(self):
        """Time of the last weather call as a UTC epoch timestamp."""
        return self._timestamp_to_utc(self._get_variable("lwc"))

    @property
    def last_successfull_weather_call(self):
        """Time of the last successful weather call as a UTC epoch
        timestamp."""
        return self._timestamp_to_utc(self._get_variable("lswc"))

    @property
    def last_weather_call_error(self):
        """Last weather call error code (0 = success)."""
        return self._get_variable("wterr")

    @property
    def last_weather_call_error_name(self):
        """Last weather call error name, or None if unknown/success."""
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
        """Today's sunrise time (minutes from midnight)."""
        return self._get_variable("sunrise")

    @property
    def sunset(self):
        """Today's sunset time (minutes from midnight)."""
        return self._get_variable("sunset")

    @property
    def last_reboot_time(self):
        """Last device reboot time as a UTC epoch timestamp."""
        return self._timestamp_to_utc(self._get_variable("lupt"))

    @property
    def last_reboot_cause(self):
        """Last device reboot cause code."""
        return self._get_variable("lrbtc")

    @property
    def last_reboot_cause_name(self):
        """Last device reboot cause name, or None if unknown."""
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
        """MQTT settings dict, or None if not supported by the firmware."""
        return self._get_variable("mqtt")

    @property
    def mqtt_enabled(self):
        """Whether MQTT is enabled, or None if not supported."""
        return (
            bool(self.mqtt_settings["en"]) if self.mqtt_settings is not None else None
        )

    @property
    def programs(self):
        """Dict of programs keyed by 0-based program index."""
        return self._programs

    @property
    def stations(self):
        """Dict of stations keyed by 0-based station index."""
        return self._stations
