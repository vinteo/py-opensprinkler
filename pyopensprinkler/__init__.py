"""Main OpenSprinkler module."""

import hashlib
import json
import urllib

import httplib2
from backoff import expo, on_exception

from pyopensprinkler.program import Program
from pyopensprinkler.station import Station


class Controller(object):
    """OpenSprinkler Controller"""

    def __init__(self, url, password, client_opts=None):
        """OpenSprinkler Controller initializer."""

        if client_opts is None:
            client_opts = {}

        self._password = password
        self._md5password = hashlib.md5(password.encode('utf-8')).hexdigest()
        self._baseUrl = url.strip("/")
        self._programs = {}
        self._stations = {}
        self._state = None

        client = httplib2.Http()
        client.follow_all_redirects = True

        if client_opts.http_username is not None:
            client.add_credentials(client_opts.http_username, client_opts.http_password)

        if client_opts.verify_ssl is not None:
            client.disable_ssl_certificate_validation = not client_opts.verify_ssl

        self._http_client = client

    def request(self, path, params=None):
        if params is None:
            params = {}
        """Make a request to the API."""
        params["pw"] = self._md5password
        qs = urllib.parse.urlencode(params)
        url = '{}{}?{}'.format(self._baseUrl, path, qs)

        return self.request_http(url)

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
        except KeyError as exc:
            raise OpenSprinklerAuthError("Invalid password") from exc

    def get_programs(self):
        """Retrieve programs"""
        if self._state is None:
            self.update()

        return self._programs

    def get_stations(self):
        """Retrieve stations"""
        if self._state is None:
            self.update()

        return self._stations

    def update(self):
        """Update programs and stations"""
        self.update_state()

        for i, _ in enumerate(self._state["programs"]["pd"]):
            if self._programs[i] is None:
                self._programs[i] = Program(self, i)

        for i, _ in enumerate(self._state["stations"]["snames"]):
            if self._stations[i] is None:
                self._stations[i] = Station(self, i)

    def update_state(self):
        (_, content) = self.request("/ja")
        self._state = content

    def _get_option(self, option):
        """Retrieve option"""
        return self._state["options"][option]

    def _get_variable(self, option):
        """Retrieve option"""
        return self._state["settings"][option]

    def _set_variable(self, option, value):
        """Retrieve option"""
        params = {option: value}
        (_, content) = self.request("/cv", params)
        self.update_state()
        return content["result"]

    @property
    def firmware_version(self):
        """Retrieve firmware version"""
        return self._get_option("fwv")

    @property
    def hardware_version(self):
        """Retrieve hardware version"""
        return self._get_option("hwv")

    @property
    def last_run(self):
        """Retrieve hardware version"""
        return self._get_variable("lrun")[3]

    @property
    def rain_delay(self):
        """Retrieve rain delay"""
        return self._get_variable("rd")

    @property
    def rain_delay_stop_time(self):
        """Retrieve rain delay stop time"""
        return self._get_variable("rdst")

    @property
    def rain_sensor_1(self):
        """Retrieve hardware version"""
        return self._get_variable("sn1")

    @property
    def rain_sensor_2(self):
        """Retrieve hardware version"""
        return self._get_variable("sn2")

    @property
    def rain_sensor_legacy(self):
        """Retrieve hardware version"""
        return self._get_variable("rs")

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

    def enable(self):
        """Enable operation"""
        return self._set_variable("en", 1)

    def disable(self):
        """Disable operation"""
        return self._set_variable("en", 0)


class OpenSprinklerAuthError(Exception):
    """Exception for authentication error."""


class OpenSprinklerConnectionError(Exception):
    """Exception for connection error."""
