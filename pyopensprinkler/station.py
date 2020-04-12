"""Station module handling /station/ API calls."""


class Station(object):
    """Station class with /station/ API calls."""

    def __init__(self, opensprinkler, station, index):
        """Station class initializer."""
        self._opensprinkler = opensprinkler
        self._station = station
        self._index = index

    @property
    def name(self):
        """Station name"""
        return self._station

    @property
    def index(self):
        """Station index"""
        return self._index

    def _getStatusVariable(self, statusIndex):
        """Retrieve seconds remaining"""
        (resp, content) = self._opensprinkler._request('jc')
        return content['ps'][self._index][statusIndex]

    def _setVariables(self, params={}):
        """Set option"""
        params['sid'] = self._index
        (resp, content) = self._opensprinkler._request('cm', params)
        return content['result']

    def getIsRunning(self):
        """Retrieve is running flag"""
        (resp, content) = self._opensprinkler._request('js')
        return content['sn'][self._index]

    def getRunningProgramId(self):
        """Retrieve seconds remaining"""
        return self._getStatusVariable(0)

    def getSecondsRemaining(self):
        """Retrieve seconds remaining"""
        return self._getStatusVariable(1)

    def getStatus(self):
        """Retrieve status"""
        isRunning = self.getIsRunning()
        pid = self.getRunningProgramId()

        if (isRunning == 1):
            if (pid == 99):
                state = "manual"
            elif (pid == 254):
                state = "once_program"
            elif (pid == 0):
                state = "idle"
            else:
                state = "program"
        else:
            if (pid > 0):
                state = "waiting"
            else:
                state = "idle"

        return state

    def run(self, seconds=60):
        """Run station"""
        params = {}
        params['en'] = 1
        params['t'] = seconds
        return self._setVariables(params)

    def stop(self):
        """Stop station"""
        params = {}
        params['en'] = 0
        return self._setVariables(params)
