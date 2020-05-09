"""Main OpenSprinkler module."""

import json
import urllib

import httplib2
from backoff import expo, on_exception
from cachetools import cached, TTLCache
from ratelimit import limits, sleep_and_retry

from pyopensprinkler.device import Device
from pyopensprinkler.program import Program
from pyopensprinkler.station import Station

_HTTP = httplib2.Http()


class OpenSprinkler(object):
    """Represent the OpenSprinkler API."""

    def __init__(self, host, md5password):
        """OpenSprinkler class initializer."""
        self._host = host
        self._md5password = md5password
        self._baseUrl = f"http://{self._host}"
        self._programs = []
        self._stations = []

        self.device = Device(self)
        self.update()

    def request(self, path, params=None):
        if params is None:
            params = {}
        """Make a request from the API."""
        params["pw"] = self._md5password
        qs = urllib.parse.urlencode(params)

        url = f"{'/'.join([self._baseUrl, path])}?{qs}"
        return self.request_http(url)

    @cached(cache=TTLCache(maxsize=4, ttl=60))
    def request_cached(self, path, params=None):
        return self.request(path, params)

    @on_exception(expo, Exception, max_tries=3)
    @sleep_and_retry
    @limits(calls=32, period=1)
    @cached(cache=TTLCache(maxsize=64, ttl=2))
    def request_http(self, url):
        try:
            (resp, content) = _HTTP.request(url, "GET")
            content = json.loads(content.decode("UTF-8"))

            if len(content) == 1 and content["fwv"]:
                raise OpensprinklerAuthError("Invalid MD5 password")

            return resp, content
        except httplib2.HttpLib2Error as exc:
            raise OpensprinklerConnectionError("Cannot connect to device") from exc
        except ConnectionError as exc:
            raise OpensprinklerConnectionError("Cannot connect to device") from exc
        except KeyError as exc:
            raise OpensprinklerAuthError("Invalid MD5 password") from exc

    def get_programs(self):
        """Retrieve programs"""
        (resp, content) = self.request("ja")
        return [
            Program(self, program, i)
            for i, program in enumerate(content["programs"]["pd"])
        ]

    def get_stations(self):
        """Retrieve stations"""
        (resp, content) = self.request("ja")
        return [
            Station(self, station, i)
            for i, station in enumerate(content["stations"]["snames"])
        ]

    def update(self):
        """Update programs and stations"""
        self._programs = self.get_programs()
        self._stations = self.get_stations()

    @property
    def programs(self):
        """Return programs"""
        return self._programs

    @property
    def stations(self):
        """Return stations"""
        return self._stations


class OpensprinklerAuthError(Exception):
    """Exception for authentication error."""


class OpensprinklerConnectionError(Exception):
    """Exception for connection error."""
