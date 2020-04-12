"""Main OpenSprinkler module."""

import httplib2
import json
import urllib

from pyopensprinkler.device import Device

_HTTP = httplib2.Http()


class OpenSprinkler(object):
    """Represent the OpenSprinkler API."""

    def __init__(self, host, md5password):
        """OpenSprinkler class initializer."""
        self._host = host
        self._md5password = md5password
        self._baseUrl = 'http://{}'.format(self._host)

        self.device = Device(self)

    def _request(self, path, method, params={}):
        """Make a request from the API."""
        params['pw'] = self._md5password
        qs = urllib.parse.urlencode(params)
        print(qs)

        url = '/'.join([self._baseUrl, path]) + '?' + qs
        print(url)
        (resp, content) = _HTTP.request(url, method)
        # TODO: check resp for errors

        content = json.loads(content.decode('UTF-8'))
        print(content)

        return (resp, content)

    def get(self, path):
        """Make a GET request from the API."""
        return self._request(path, 'GET')
