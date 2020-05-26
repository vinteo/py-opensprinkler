"""Program module handling /program/ API calls."""

import json


class Program(object):
    """Program class with /program/ API calls."""

    def __init__(self, controller, index):
        """Program class initializer."""
        self._controller = controller
        self._index = index

    def _get_program_data(self):
        return self._controller._state["programs"]["pd"][self._index]

    def _get_variable(self, variable_index):
        """Retrieve variable"""
        return self._get_program_data()[variable_index]

    def _set_variable(self, variable, value):
        """Set variable"""
        return self._set_variables({variable: value})

    def _set_variables(self, params=None):
        if params is None:
            params = {}
        params["pid"] = self._index

        # hacky garbage to make setting the name work
        # NOTE: setting en and name in the same request results in the name parameter being ignored
        v = ""
        if "v" not in params:
            dlist = self._get_program_data().copy()
            if "name" in params:
                dlist.pop(5)
            v = json.dumps(dlist).replace(" ", "")

        if "v" in params:
            name = params["v"].pop(5)
            if "name" not in params:
                params["name"] = name
            v = json.dumps(params.pop("v", None)).replace(" ", "")

        v = v.strip()

        (_, content) = self._controller.request("/cp", params, f"v={v}")
        return content["result"]

    def _manual_run(self):
        """Run program"""
        params = {"pid": self._index, "uwt": 0}
        (_, content) = self._controller.request("/mp", params)
        return content["result"]

    def _get_data_flag_bits(self):
        return list(
            reversed([int(x) for x in list("{0:08b}".format(self._get_variable(0)))])
        )

    def _set_data_flag_bit(self, index, value):
        print("foo")

    def enable(self):
        """Enable operation"""
        return self.set_enabled(True)

    def disable(self):
        """Disable operation"""
        return self.set_enabled(False)

    def set_enabled(self, value):
        if value:
            return self._set_variable("en", 1)
        else:
            return self._set_variable("en", 0)

    def run(self):
        """Run program"""
        return self._manual_run()

    def set_name(self, name):
        return self._set_variable("name", name)

    def set_use_weather_adjustments(self, value):
        return self._set_variable("uwt", int(value))

    def set_odd_even_restriction(self, value):
        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()

        if value < 0 or value > 3:
            raise ValueError("value must be 0-3")

        if value == 3:
            raise ValueError("value must not be 3")

        # none
        if value == 0:
            bits[2] = 0
            bits[3] = 0

        # odd-days
        if value == 1:
            bits[2] = 1
            bits[3] = 0

        # even-days
        if value == 2:
            bits[2] = 0
            bits[3] = 1

        # undefined
        if value == 3:
            bits[2] = 1
            bits[3] = 1

        bits = list(reversed(bits))
        bits = "".join(map(str, bits))
        bits = int(bits, 2)

        dlist[0] = bits

        return self._set_variable("v", dlist)

    def set_program_schedule_type(self, value):
        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()

        if value < 0 or value > 3:
            raise ValueError("value must be 0-3")

        if value != 0 and value != 3:
            raise ValueError("value must be 0 or 3")

        # weekday
        if value == 0:
            bits[4] = 0
            bits[5] = 0

        # undefined
        if value == 1:
            bits[4] = 1
            bits[5] = 0

        # undefined
        if value == 2:
            bits[4] = 0
            bits[5] = 1

        # interval-day
        if value == 3:
            bits[4] = 1
            bits[5] = 1

        bits = list(reversed(bits))
        bits = "".join(map(str, bits))
        bits = int(bits, 2)

        dlist[0] = bits

        return self._set_variable("v", dlist)

    def set_start_time_type(self, value):
        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()

        if value < 0 or value > 1:
            raise ValueError("value must be 0 or 1")

        # repeating
        if value == 0:
            bits[6] = 0

        # fixed-time
        if value == 1:
            bits[6] = 1

        bits = list(reversed(bits))
        bits = "".join(map(str, bits))
        bits = int(bits, 2)

        dlist[0] = bits

        return self._set_variable("v", dlist)

    def set_station_duration(self, station_index, duration):
        dlist = self._get_program_data().copy()
        dlist[4][station_index] = duration
        return self._set_variable("v", dlist)

    def set_station_durations(self, durations):
        dlist = self._get_program_data().copy()
        dlist[4] = durations
        return self._set_variable("v", dlist)

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
        bits = self._get_data_flag_bits()
        return bool(bits[0])

    @property
    def is_running(self):
        for _, station in self._controller.stations.items():
            if (
                station.is_running
                and station.running_program_id > 0
                and station.running_program_id == self.index + 1
            ):
                return True

        return False

    @property
    def use_weather_adjustments(self):
        """Retrieve use weather adjustment flag"""
        bits = self._get_data_flag_bits()
        return bool(bits[1])

    @property
    def odd_even_restriction(self):
        """Retrieve odd/even restriction state"""
        bit2 = bool(self._get_data_flag_bits()[2])
        bit3 = bool(self._get_data_flag_bits()[3])

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
            return "odd-days"

        if value == 2:
            return "even-days"

    @property
    def program_schedule_type(self):
        """Retrieve program schedule type state"""
        bit4 = bool(self._get_data_flag_bits()[4])
        bit5 = bool(self._get_data_flag_bits()[5])

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
        return self._get_data_flag_bits()[6]

    @property
    def start_time_type_name(self):
        value = self.start_time_type

        if value == 0:
            return "repeating"

        if value == 1:
            return "fixed-time"
