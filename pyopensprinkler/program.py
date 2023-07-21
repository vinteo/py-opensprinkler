"""Program module handling /program/ API calls."""

import json

from pyopensprinkler.const import (
    SCHEDULE_START_TIME_FIXED,
    SCHEDULE_START_TIME_REPEATING,
    SCHEDULE_TYPE_INTERVAL_DAY,
    SCHEDULE_TYPE_WEEKDAY,
)


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

    async def _set_variable(self, variable, value):
        """Set variable"""
        return await self._set_variables({variable: value})

    async def _set_variables(self, params=None):
        if params is None:
            params = {}
        params["pid"] = self._index

        content = await self._controller.request("/cp", params)
        return content["result"]

    async def _manual_run(self):
        """Run program"""
        params = {"pid": self._index, "uwt": 0}
        content = await self._controller.request("/mp", params)
        return content["result"]

    def _get_data_flag_bits(self):
        return list(
            reversed([int(x) for x in list("{0:08b}".format(self._get_variable(0)))])
        )

    def _bits_to_int(self, bits):
        return int("".join(map(str, list(reversed(bits)))), 2)

    def _format_program_data(self, dlist):
        """Move program name from 'v' to 'name' parameter and remove spaces."""
        name = dlist.pop(5)
        v = json.dumps(dlist).replace(" ", "")
        params = {"v": v, "name": name}
        return params

    async def enable(self):
        """Enable operation"""
        return await self.set_enabled(True)

    async def disable(self):
        """Disable operation"""
        return await self.set_enabled(False)

    async def set_enabled(self, value):
        if value:
            return await self._set_variable("en", 1)
        else:
            return await self._set_variable("en", 0)

    async def run(self):
        """Run program"""
        return await self._manual_run()

    async def set_name(self, name):
        dlist = self._get_program_data().copy()
        dlist[5] = name
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_use_weather_adjustments(self, value):
        return await self._set_variable("uwt", int(value))

    async def set_odd_even_restriction(self, value):
        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()

        if value < 0 or value > 2:
            raise ValueError("value must be 0-2")

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

        dlist[0] = self._bits_to_int(bits)
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_schedule_type(self, value):
        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()

        if value != 0 and value != 3:
            raise ValueError("value must be 0 or 3")

        # weekday
        if value == 0:
            bits[4] = 0
            bits[5] = 0

        # interval-day
        if value == 3:
            bits[4] = 1
            bits[5] = 1

        dlist[0] = self._bits_to_int(bits)
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_start_time_type(self, value):
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

        dlist[0] = self._bits_to_int(bits)
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_time(self, start_index, start_time):
        dlist = self._get_program_data().copy()
        dlist[3][start_index] = start_time
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_times(self, start_times):
        dlist = self._get_program_data().copy()
        dlist[3] = start_times
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_station_duration(self, station_index, duration):
        dlist = self._get_program_data().copy()
        dlist[4][station_index] = duration
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_station_durations(self, durations):
        dlist = self._get_program_data().copy()
        dlist[4] = durations
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_days0(self, value):
        """Set days0 (weekday bits in Weekday mode, starting in days in Interval mode)"""
        dlist = self._get_program_data().copy()
        dlist[1] = value
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_days1(self, value):
        """Retrieve days1 (not used in Weekday mode, interval days in Interval mode)"""
        dlist = self._get_program_data().copy()
        dlist[2] = value
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

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
            return "odd_days"

        if value == 2:
            return "even_days"

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
            return SCHEDULE_TYPE_WEEKDAY

        if value == 3:
            return SCHEDULE_TYPE_INTERVAL_DAY

        return None

    @property
    def start_time_type(self):
        return self._get_data_flag_bits()[6]

    @property
    def start_time_type_name(self):
        value = self.start_time_type

        if value == 0:
            return SCHEDULE_START_TIME_REPEATING

        if value == 1:
            return SCHEDULE_START_TIME_FIXED

    @property
    def program_start_times(self):
        """Retrieve station start times"""
        return self._get_variable(3)

    @property
    def station_durations(self):
        """Retrieve station durations"""
        return self._get_variable(4)

    @property
    def days0(self):
        """Retrieve days0 (weekday bits in Weekday mode, starting in days in Interval mode)"""
        return self._get_variable(1)

    @property
    def days1(self):
        """Retrieve days1 (not used in Weekday mode, interval days in Interval mode)"""
        return self._get_variable(2)
