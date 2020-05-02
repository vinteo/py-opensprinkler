"""Main OpenSprinkler module."""

import json
import urllib

import httplib2
from cachetools import cached, TTLCache

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

        self.device = Device(self)

    def request(self, path, params=None):
        if params is None:
            params = {}
        """Make a request from the API."""
        params["pw"] = self._md5password
        qs = urllib.parse.urlencode(params)

        url = f"{'/'.join([self._baseUrl, path])}?{qs}"
        return self.request_http(url)

    @cached(cache=TTLCache(maxsize=32, ttl=1))
    def request_http(self, url):
        (resp, content) = _HTTP.request(url, "GET")
        # TODO: check resp for errors
        content = json.loads(content.decode("UTF-8"))
        return resp, content

    @property
    def programs(self):
        """Retrieve programs"""
        (resp, content) = self.request("jp")
        return [Program(self, program, i) for i, program in enumerate(content["pd"])]

    @property
    def stations(self):
        """Retrieve stations"""
        (resp, content) = self.request("jn")
        return [
            Station(self, station, i) for i, station in enumerate(content["snames"])
        ]
