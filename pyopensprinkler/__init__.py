"""Main OpenSprinkler module."""

import hashlib
import json
import time
import urllib

import httplib2
from backoff import expo, on_exception

from pyopensprinkler.program import Program
from pyopensprinkler.station import Station


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
        self.refresh_on_update = None

        client = httplib2.Http()
        client.follow_all_redirects = True

        if "auto_refresh_on_update" not in opts:
            opts["auto_refresh_on_update"] = {}

        if "enabled" not in opts["auto_refresh_on_update"]:
            opts["auto_refresh_on_update"]["enabled"] = True

        if "settle_time" not in opts["auto_refresh_on_update"]:
            opts["auto_refresh_on_update"]["settle_time"] = 1

        if "http_username" in opts:
            client.add_credentials(opts.http_username, opts.http_password)

        if "verify_ssl" in opts:
            client.disable_ssl_certificate_validation = not opts.verify_ssl

        self._http_client = client

    def request(self, path, params=None, raw_qs=None, refresh_on_update=None):
        if params is None:
            params = {}
        """Make a request to the API."""
        params["pw"] = self._md5password
        qs = urllib.parse.urlencode(params)
        if raw_qs is not None and len(raw_qs) > 0:
            qs = qs + "&" + raw_qs
        url = f"{self._baseUrl}{path}?{qs}"

        (resp, content) = self.request_http(url)

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
            time.sleep(float(self._opts["auto_refresh_on_update"]["settle_time"]))
            self.refresh()

        return resp, content

    @on_exception(expo, Exception, max_tries=3)
    def request_http(self, url):
        try:
            (resp, content) = self._http_client.request(url, "GET")
            content = json.loads(content.decode("UTF-8"))

            if len(content) == 1 and not content["result"] and content["fwv"]:
                raise OpenSprinklerAuthError("Invalid password")

            return resp, content
        except httplib2.HttpLib2Error as exc:
            raise OpenSprinklerConnectionError("Cannot connect to controller") from exc
        except ConnectionError as exc:
            raise OpenSprinklerConnectionError("Cannot connect to controller") from exc
        except json.decoder.JSONDecodeError as exc:
            raise OpenSprinklerConnectionError("Cannot connect to controller") from exc
        except KeyError as exc:
            raise OpenSprinklerAuthError("Invalid password") from exc

    def refresh(self):
        """Refresh programs and stations"""
        self._refresh_state()

        for i, _ in enumerate(self._state["programs"]["pd"]):
            if i not in self._programs:
                self._programs[i] = Program(self, i)

        for i, _ in enumerate(self._state["stations"]["snames"]):
            if i not in self._stations:
                self._stations[i] = Station(self, i)

    def _refresh_state(self):
        (_, content) = self.request("/ja")
        self._state = content

    def _get_option(self, option):
        """Retrieve option"""
        return self._state["options"][option]

    def _get_options(self):
        """Retrieve options"""
        return self._state["options"]

    def _set_option(self, option, value):
        """Set option"""
        params = {option: value}
        (_, content) = self.request("/co", params)
        return content["result"]

    def _set_options(self, options):
        """Set options"""
        (_, content) = self.request("/co", options)
        return content["result"]

    def _get_variable(self, option):
        """Retrieve variable"""
        return self._state["settings"][option]

    def _get_variables(self):
        """Retrieve variables"""
        return self._state["settings"]

    def _set_variable(self, variable, value):
        """Set variable"""
        params = {variable: value}
        (_, content) = self.request("/cv", params)
        return content["result"]

    def _set_variables(self, variables):
        """Set variables"""
        (_, content) = self.request("/cv", variables)
        return content["result"]

    # controller variables
    def enable(self):
        """Enable operation"""
        return self._set_variable("en", 1)

    def disable(self):
        """Disable operation"""
        return self._set_variable("en", 0)

    def reboot(self):
        return self._set_variable("rbt", 1)

    def set_rain_delay(self, hours):
        """
        Set rain delay time (in hours). Range is 0 to 32767. A value of 0 turns off rain delay.
        """

        if hours < 0 or hours > 32767:
            raise ValueError("level must be 0-32767")

        return self._set_variable("rd", hours)

    def disable_rain_delay(self):
        return self._set_variable("rd", 0)

    def enable_remote_extension_mode(self):
        return self._set_variable("re", 1)

    def disable_remote_extension_mode(self):
        return self._set_variable("re", 0)

    def stop_all_stations(self):
        return self._set_variable("rsn", 1)

    def firmware_update(self):
        return self._set_variable("update", 1)

    # controller options
    def set_water_level(self, level):
        """
        Water level (i.e. % Watering). Acceptable range is 0 to 250.
        """

        if level < 0 or level > 250:
            raise ValueError("level must be 0-250")

        return self._set_option("wl", level)

    @property
    def firmware_version(self):
        """Retrieve firmware version"""
        return self._get_option("fwv")

    @property
    def hardware_version(self):
        """Retrieve hardware version"""
        return self._get_option("hwv")

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
        return self._get_variable("lrun")[3]

    @property
    def rain_delay_enabled(self):
        """Retrieve rain delay enabled"""
        return bool(self._get_variable("rd"))

    @property
    def rain_delay_stop_time(self):
        """Retrieve rain delay stop time"""
        return self._get_variable("rdst")

    @property
    def rain_sensor_enabled(self):
        """Retrieve rain sensor enabled"""
        try:
            return bool(self._get_variable("rs"))
        except KeyError:
            return None

    @property
    def sensor_1_enabled(self):
        """Retrieve sensor 1 enabled"""
        return bool(self._get_variable("sn1"))

    @property
    def sensor_2_enabled(self):
        """Retrieve sensor 2 enabled"""
        return bool(self._get_variable("sn2"))

    @property
    def operation_enabled(self):
        """Retrieve operation enabled"""
        return self._get_variable("en")

    @property
    def water_level(self):
        """Retrieve water level"""
        return self._get_option("wl")

    @property
    def programs(self):
        """Return programs"""
        return self._programs

    @property
    def stations(self):
        """Return stations"""
        return self._stations


class OpenSprinklerAuthError(Exception):
    """Exception for authentication error."""


class OpenSprinklerConnectionError(Exception):
    """Exception for connection error."""
