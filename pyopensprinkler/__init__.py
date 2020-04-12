"""Main OpenSprinkler module."""

import httplib2
import json
import urllib

from pyopensprinkler.device import Device
from pyopensprinkler.program import Program

_HTTP = httplib2.Http()


class OpenSprinkler(object):
    """Represent the OpenSprinkler API."""

    def __init__(self, host, md5password):
        """OpenSprinkler class initializer."""
        self._host = host
        self._md5password = md5password
        self._baseUrl = 'http://{}'.format(self._host)

        self.device = Device(self)

        self.getPrograms()

    def _request(self, path, params={}):
        """Make a request from the API."""
        params['pw'] = self._md5password
        qs = urllib.parse.urlencode(params)
        print(qs)

        url = '/'.join([self._baseUrl, path]) + '?' + qs
        print(url)
        (resp, content) = _HTTP.request(url, 'GET')
        # TODO: check resp for errors

        content = json.loads(content.decode('UTF-8'))
        print(content)

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
