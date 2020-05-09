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

    def _get_variable(self, variable_index):
        """Retrieve option"""
        return self._opensprinkler._state["programs"]["pd"][self._index][variable_index]

    def _set_variable(self, option, value):
        """Set option"""
        params = {"pid": self._index, option: value}
        (resp, content) = self._opensprinkler.request("cp", params)
        self._opensprinkler.update_state()
        return content["result"]

    def _activate(self):
        """Run program"""
        params = {"pid": self._index, "uwt": 0}
        (resp, content) = self._opensprinkler.request("mp", params)
        self._opensprinkler.update_state()
        return content["result"]

    @property
    def enabled(self):
        """Retrieve enabled flag"""
        return int("{0:08b}".format(self._get_variable(0))[7])

    def enable(self):
        """Enable operation"""
        return self._set_variable("en", 1)

    def disable(self):
        """Disable operation"""
        return self._set_variable("en", 0)

    def run(self):
        """Run program"""
        return self._activate()
