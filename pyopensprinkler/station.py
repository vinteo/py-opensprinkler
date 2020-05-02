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

    def _get_status_variable(self, statusIndex):
        """Retrieve seconds remaining"""
        (resp, content) = self._opensprinkler.request("jc")
        return content["ps"][self._index][statusIndex]

    def _set_variables(self, params=None):
        """Set option"""
        if params is None:
            params = {}
        params["sid"] = self._index
        (resp, content) = self._opensprinkler.request("cm", params)
        return content["result"]

    @property
    def is_running(self):
        """Retrieve is running flag"""
        (resp, content) = self._opensprinkler.request("js")
        return content["sn"][self._index]

    @property
    def running_program_id(self):
        """Retrieve seconds remaining"""
        return self._get_status_variable(0)

    @property
    def seconds_remaining(self):
        """Retrieve seconds remaining"""
        return self._get_status_variable(1)

    @property
    def status(self):
        """Retrieve status"""
        is_running = self.is_running
        pid = self.running_program_id

        if is_running == 1:
            if pid == 99:
                state = "manual"
            elif pid == 254:
                state = "once_program"
            elif pid == 0:
                state = "idle"
            else:
                state = "program"
        else:
            if pid > 0:
                state = "waiting"
            else:
                state = "idle"

        return state

    def run(self, seconds=60):
        """Run station"""
        params = {"en": 1, "t": seconds}
        return self._set_variables(params)

    def stop(self):
        """Stop station"""
        params = {"en": 0}
        return self._set_variables(params)
