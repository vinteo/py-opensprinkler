"""Program module handling /program/ API calls."""


class Program(object):
    """Program class with /program/ API calls."""

    def __init__(self, controller, index):
        """Program class initializer."""
        self._controller = controller
        self._index = index

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
        return list(
            reversed([int(x) for x in list("{0:08b}".format(self._get_variable(0)))])
        )

    def enable(self):
        """Enable operation"""
        return self._set_variable("en", 1)

    def disable(self):
        """Disable operation"""
        return self._set_variable("en", 0)

    def run(self):
        """Run program"""
        return self._manual_run()

    @property
    def name(self):
        """Program name"""
        return self._get_variable(5)

    @property
    def index(self):
        """Program index"""
        return self._index

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

    @property
    def odd_even_restriction(self):
        """Retrieve odd/even restriction state"""
        bit2 = bool(self._get_data_bits()[2])
        bit3 = bool(self._get_data_bits()[3])

        value = 0
        if bit2:
            value += 1

        if bit3:
            value += 2

        return value

    @property
    def odd_even_restriction_name(self):
        value = self.odd_even_restriction

        if value == 0 or value == 3:
            return None

        if value == 1:
            return "odd-day"

        if value == 2:
            return "even-day"

    @property
    def program_schedule_type(self):
        """Retrieve program schedule type state"""
        bit4 = bool(self._get_data_bits()[4])
        bit5 = bool(self._get_data_bits()[5])

        value = 0
        if bit4:
            value += 1

        if bit5:
            value += 2

        return value

    @property
    def program_schedule_type_name(self):
        value = self.program_schedule_type

        if value == 0:
            return "weekday"

        if value == 3:
            return "interval-day"

        return None

    @property
    def start_time_type(self):
        return self._get_data_bits()[6]

    @property
    def start_time_type_name(self):
        value = self.start_time_type

        if value == 0:
            return "repeating"

        if value == 1:
            return "fixed-time"
