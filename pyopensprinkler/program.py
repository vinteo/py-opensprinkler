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
        return content["result"]

    def _manual_run(self):
        """Run program"""
        params = {"pid": self._index, "uwt": 0}
        (_, content) = self._controller.request("/mp", params)
        return content["result"]

    def _get_data_bits(self):
        return list(reversed([int(x) for x in list('{0:08b}'.format(self._get_variable(0)))]))

    @property
    def enabled(self):
        """Retrieve enabled flag"""
        bits = self._get_data_bits()
        return bool(bits[0])

    @property
    def use_weather_adjustments(self):
        """Retrieve use weather adjustment flag"""
        bits = self._get_data_bits()
        return bool(bits[1])

    def enable(self):
        """Enable operation"""
        return self._set_variable("en", 1)

    def disable(self):
        """Disable operation"""
        return self._set_variable("en", 0)

    def run(self):
        """Run program"""
        return self._manual_run()
