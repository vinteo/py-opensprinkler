"""Device module handling /device/ API calls."""


class Device(object):
    """Device class with /device/ API calls."""

    def __init__(self, opensprinkler):
        """Device class initializer."""
        self._opensprinkler = opensprinkler

    def _get_option(self, option):
        """Retrieve option"""
        (resp, content) = self._opensprinkler.request("jo")
        return content[option]

    def _get_variable(self, option):
        """Retrieve option"""
        (resp, content) = self._opensprinkler.request("jc")
        return content[option]

    def _set_variable(self, option, value):
        """Retrieve option"""
        params = {option: value}
        (resp, content) = self._opensprinkler.request("cv", params)
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

    def enable(self):
        """Enable operation"""
        return self._set_variable("en", 1)

    def disable(self):
        """Disable operation"""
        return self._set_variable("en", 0)
