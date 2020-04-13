"""Main OpenSprinkler module."""

import httplib2
import json
import urllib

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

        self.getPrograms()
        self.getStations()

    def _request(self, path, params={}):
        """Make a request from the API."""
        params['pw'] = self._md5password
        qs = urllib.parse.urlencode(params)

        url = f"{'/'.join([self._baseUrl, path])}?{qs}"
        (resp, content) = _HTTP.request(url, 'GET')
        # TODO: check resp for errors

        content = json.loads(content.decode('UTF-8'))

        return (resp, content)

    def getPrograms(self):
        """Retrieve programs"""
        (resp, content) = self._request('jp')

        self._programs = []
        for i, program in enumerate(content['pd']):
            self._programs.append(Program(self, program, i))

        return self._programs

    def getProgram(self, index):
        """Retrieve program"""
        return self._programs[index]

    def getStations(self):
        """Retrieve stations"""
        (resp, content) = self._request('jn')

        self._stations = []
        for i, station in enumerate(content['snames']):
            self._stations.append(Station(self, station, i))

        return self._stations

    def getStation(self, index):
        """Retrieve station"""
        return self._stations[index]
