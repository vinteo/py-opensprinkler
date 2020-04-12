"""Program module handling /program/ API calls."""


class Program(object):
    """Program class with /program/ API calls."""

    def __init__(self, opensprinkler, program, index):
        """Program class initializer."""
        self._opensprinkler = opensprinkler
        self._program = program
        self._index = index

    @property
    def name(self):
        """Program name"""
        return self._program[5]

    @property
    def index(self):
        """Program index"""
        return self._index

    def _getVariable(self, variableIndex):
        """Retrieve option"""
        (resp, content) = self._opensprinkler._request('jp')
        return content['pd'][self._index][variableIndex]

    def _setVariable(self, option, value):
        """Set option"""
        params = {}
        params['pid'] = self._index
        params[option] = value
        (resp, content) = self._opensprinkler._request('cp', params)
        return content['result']

    def getEnabled(self):
        """Retrieve enabled flag"""
        return int('{0:08b}'.format(self._getVariable(0))[7])

    def enable(self):
        """Enable operation"""
        return self._setVariable('en', 1)

    def disable(self):
        """Disable operation"""
        return self._setVariable('en', 0)

    def run(self):
        """Run program"""
        return self._setVariable('uwt', 0)
