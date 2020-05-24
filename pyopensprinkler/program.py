"""Program module handling /program/ API calls."""


class Program(object):
    """Program class with /program/ API calls."""

    def __init__(self, controller, index):
        """Program class initializer."""
        self._controller = controller
        self._index = index

    @property
    def name(self):
        """Program name"""
        return self._get_variable(5)

    @property
    def index(self):
        """Program index"""
        return self._index

    def _get_program_data(self):
        return self._controller._state["programs"]["pd"][self._index]

    def _get_variable(self, variable_index):
        """Retrieve option"""
        return self._get_program_data()[variable_index]

    def _set_variable(self, option, value):
        """Set option"""
        params = {"pid": self._index, option: value}
        (_, content) = self._controller.request("/cp", params)
        self._controller.update_state()
        return content["result"]

    def _activate(self):
        """Run program"""
        params = {"pid": self._index, "uwt": 0}
        (_, content) = self._controller.request("/mp", params)
        self._controller.update_state()
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
