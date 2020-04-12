"""Device module handling /device/ API calls."""


class Device(object):
    """Device class with /device/ API calls."""

    def __init__(self, opensprinkler):
        """Device class initializer."""
        self.opensprinkler = opensprinkler

    def _getOption(self, option):
        """Retrieve option"""
        (resp, content) = self.opensprinkler.get('jo')
        return content[option]

    def getFirmwareVersion(self):
        """Retrieve firmware version"""
        return self._getOption('fwv')

    def getHardwareVersion(self):
        """Retrieve hardware version"""
        return self._getOption('hwv')
