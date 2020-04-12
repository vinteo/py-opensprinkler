"""Device module handling /device/ API calls."""


class Device(object):
    """Device class with /device/ API calls."""

    def __init__(self, opensprinkler):
        """Device class initializer."""
        self.opensprinkler = opensprinkler

    def _getOption(self, option):
        """Retrieve option"""
        (resp, content) = self.opensprinkler._request('jo')
        return content[option]

    def _getVariable(self, option):
        """Retrieve option"""
        (resp, content) = self.opensprinkler._request('jc')
        return content[option]

    def _setVariable(self, option, value):
        """Retrieve option"""
        params = {}
        params[option] = value
        (resp, content) = self.opensprinkler._request('cv', params)
        return content['result']

    def getFirmwareVersion(self):
        """Retrieve firmware version"""
        return self._getOption('fwv')

    def getHardwareVersion(self):
        """Retrieve hardware version"""
        return self._getOption('hwv')

    def getLastRun(self):
        """Retrieve hardware version"""
        return self._getVariable('lrun')

    def getRainDelay(self):
        """Retrieve rain delay"""
        return self._getVariable('rd')

    def getRainDelayStopTime(self):
        """Retrieve rain delay stop time"""
        return self._getVariable('rdst')

    def getRainSensor1(self):
        """Retrieve hardware version"""
        return self._getVariable('sn1')

    def getRainSensor2(self):
        """Retrieve hardware version"""
        return self._getVariable('sn2')

    def getRainSensorLegacy(self):
        """Retrieve hardware version"""
        return self._getVariable('rs')

    def getOperationEnabled(self):
        """Retrieve operation enabled"""
        return self._getVariable('en')

    def enable(self):
        """Enable operation"""
        return self._setVariable('en', 1)

    def disable(self):
        """Disable operation"""
        return self._setVariable('en', 0)
