"""Program module handling /program/ API calls."""

import json

from pyopensprinkler.const import (
    SCHEDULE_START_TIME_FIXED,
    SCHEDULE_START_TIME_OFFSET_DISABLED,
    SCHEDULE_START_TIME_OFFSET_MIDNIGHT,
    SCHEDULE_START_TIME_OFFSET_SUNRISE,
    SCHEDULE_START_TIME_OFFSET_SUNSET,
    SCHEDULE_START_TIME_REPEATING,
    SCHEDULE_TYPE_INTERVAL_DAY,
    SCHEDULE_TYPE_WEEKDAY,
    START_TIME_MINUTES_MASK,
    START_TIME_SIGN_BIT,
    START_TIME_SUNRISE_BIT,
    START_TIME_SUNSET_BIT,
    WEEKDAYS,
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

    def _is_set(self, x, n):
        """Test for nth bit set."""
        return x & 1 << n != 0

    def _bit_set(self, x, n, state=True):
        """Set or clear nth bit."""
        if state:
            return x | 1 << n
        else:
            return x & ~(1 << n)

    def _get_offset_minutes(self, start_times, start_index):
        """Extract offset minutes from encoded start time"""
        sign = -1 if self._is_set(start_times[start_index], START_TIME_SIGN_BIT) else 1
        use_sunset = bool(self._is_set(start_times[start_index], START_TIME_SUNSET_BIT))
        use_sunrise = bool(
            self._is_set(start_times[start_index], START_TIME_SUNRISE_BIT)
        )

        if start_times[start_index] == -1:  # disabled
            return 0
        # Only start0 has offset if repeating type
        elif start_index > 0 and self.start_time_type == 0:
            return 0
        elif use_sunset:
            return (start_times[start_index] & START_TIME_MINUTES_MASK) * sign
        elif use_sunrise:
            return (start_times[start_index] & START_TIME_MINUTES_MASK) * sign
        else:
            return start_times[start_index]

    def _encode_offset_minutes(self, offset_type, start_time_offset):
        """Encode start time with offset minutes, sign bit, and sunset/sunrise bit"""
        new_sign_bit = 1 if start_time_offset < 0 else 0

        if offset_type == SCHEDULE_START_TIME_OFFSET_DISABLED:
            return -1
        elif offset_type == SCHEDULE_START_TIME_OFFSET_SUNSET:
            return (
                abs(int(start_time_offset))
                | (new_sign_bit << START_TIME_SIGN_BIT)
                | (1 << START_TIME_SUNSET_BIT)
            )
        elif offset_type == SCHEDULE_START_TIME_OFFSET_SUNRISE:
            return (
                abs(int(start_time_offset))
                | (new_sign_bit << START_TIME_SIGN_BIT)
                | (1 << START_TIME_SUNRISE_BIT)
            )
        else:
            return start_time_offset

    def _get_offset_type(self, start_times, start_index):
        """Get start time offset type ('disabled', 'midnight', 'sunset', or 'sunrise')"""
        use_sunset = bool(self._is_set(start_times[start_index], START_TIME_SUNSET_BIT))
        use_sunrise = bool(
            self._is_set(start_times[start_index], START_TIME_SUNRISE_BIT)
        )

        if start_times[start_index] == -1:
            return SCHEDULE_START_TIME_OFFSET_DISABLED
        # Only start0 has offset if repeating type
        elif start_index > 0 and self.start_time_type == 0:
            return None
        elif use_sunset:
            return SCHEDULE_START_TIME_OFFSET_SUNSET
        elif use_sunrise:
            return SCHEDULE_START_TIME_OFFSET_SUNRISE
        else:
            return SCHEDULE_START_TIME_OFFSET_MIDNIGHT

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
            raise ValueError("Value must be 0-2")

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
            raise ValueError("Value must be 0 or 3")

        # weekday
        if value == 0:
            bits[4] = 0
            bits[5] = 0

        # interval-day
        if value == 3:
            bits[4] = 1
            bits[5] = 1

        # If changing type, data in days0-1 becomes meaningless, so set to default.
        if dlist[0] != self._bits_to_int(bits):
            dlist[1] = 0
            dlist[2] = 0 if value == 0 else 1  # Interval day must be >= 1
            dlist[0] = self._bits_to_int(bits)
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_start_time_type(self, value):
        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()

        if value < 0 or value > 1:
            raise ValueError("Value must be 0 or 1")

        # repeating
        if value == 0:
            bits[6] = 0

        # fixed-time
        if value == 1:
            bits[6] = 1

        # If changing type, data in start1-3 becomes meaningless, so set to default.
        if dlist[0] != self._bits_to_int(bits):
            dlist[3][1] = 0 if value == 0 else -1
            dlist[3][2] = 0 if value == 0 else -1
            dlist[3][3] = 0 if value == 0 else -1
            dlist[0] = self._bits_to_int(bits)
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_time(self, start_index, start_time):
        """Set program start time with encoded value for start0, 1, 2, or 3"""
        if not 0 <= start_index <= 3:
            raise IndexError("start_index must be between 0 and 3")
        dlist = self._get_program_data().copy()
        dlist[3][start_index] = start_time
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_times(self, start_times):
        """Set program start times with encoded list for start0-start3"""
        dlist = self._get_program_data().copy()
        dlist[3] = start_times
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_time_offset(self, start_index, start_time_offset):
        """Set program start time offset in minutes without chaning current offset type"""
        if not 0 <= start_index <= 3:
            raise IndexError("start_index must be between 0 and 3")

        # Only start0 has offset if repeating type
        if start_index > 0 and self.start_time_type == 0:
            raise RuntimeError(
                f"Cannot update start{start_index} with minutes when start time type is 'repeating'"
            )

        dlist = self._get_program_data().copy()
        current_offset_type = self._get_offset_type(dlist[3], start_index)

        # Assume offset of midnight if attempting to set new start time
        if current_offset_type == "disabled":
            current_offset_type = "midnight"

        new_start = self._encode_offset_minutes(current_offset_type, start_time_offset)
        dlist[3][start_index] = new_start
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_time_offset_type(
        self, start_index, start_time_offset_type
    ):
        """Set program start time offset type ('disabled', 'midnight', 'sunset', or 'sunrise'). Resets minutes to 0."""
        if not 0 <= start_index <= 3:
            raise IndexError("start_index must be between 0 and 3")

        # Only start0 has offset if repeating type
        if start_index > 0 and self.start_time_type == 0:
            raise RuntimeError(
                f"Cannot update start{start_index} offset type when start time type is 'repeating'"
            )

        valid_options = ["disabled", "midnight", "sunset", "sunrise"]
        if start_time_offset_type not in valid_options:
            raise ValueError(
                "start_time_offset_type must be one of {}".format(valid_options)
            )

        dlist = self._get_program_data().copy()
        new_start = self._encode_offset_minutes(start_time_offset_type, 0)
        dlist[3][start_index] = new_start
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_repeat_count(self, repeat_count):
        """Set program start repeat count"""
        if self.start_time_type == 1:
            raise RuntimeError(
                "Cannot update repeat count when start time type is 'fixed'"
            )

        dlist = self._get_program_data().copy()
        dlist[3][1] = repeat_count
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_repeat_interval(self, repeat_minutes):
        """Set program start repeat interval in minutes"""
        if self.start_time_type == 1:
            raise RuntimeError(
                "Cannot update repeat count when start time type is 'fixed'"
            )

        dlist = self._get_program_data().copy()
        dlist[3][2] = repeat_minutes
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_weekday_enabled(self, weekday, enabled):
        """Set program weekday enabled state (weekday = 'Monday', 'Tuesday', etc.)"""
        if self.program_schedule_type == 3:
            raise RuntimeError(
                "Cannot update Weekly schedule when schedule type is 'Interval'"
            )

        dlist = self._get_program_data().copy()
        dlist[1] = self._bit_set(dlist[1], WEEKDAYS.index(weekday), enabled)
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
        """Set days1 (not used in Weekday mode, interval days in Interval mode)"""
        dlist = self._get_program_data().copy()
        dlist[2] = value
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_starting_in_days(self, value):
        """Set days0, starting in days in Interval mode)"""
        if self.program_schedule_type == 0:
            raise RuntimeError(
                "Cannot update Starting In Days when schedule type is 'Weekday'"
            )

        dlist = self._get_program_data().copy()
        dlist[1] = value
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_interval_days(self, value):
        """Set days1, interval days in Interval mode)"""
        if self.program_schedule_type == 0:
            raise RuntimeError(
                "Cannot update Interval Days when schedule type is 'Weekday'"
            )

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

    def get_program_start_time(self, start_index):
        """Retrieve program start time in encoded value"""
        return self._get_variable(3)[start_index]

    @property
    def program_start_times(self):
        """Retrieve program start times in list of encoded values"""
        return self._get_variable(3)

    def get_program_start_time_offset(self, start_index):
        """Retrieve program start time offset in minutes"""
        if not 0 <= start_index <= 3:
            raise IndexError("start_index must be between 0 and 3")

        start_times = self._get_variable(3)
        return self._get_offset_minutes(start_times, start_index)

    @property
    def program_start_time_offsets(self):
        """Retrieve program start time offsets in minutes"""
        return [
            self.get_program_start_time_offset(0),
            self.get_program_start_time_offset(1),
            self.get_program_start_time_offset(2),
            self.get_program_start_time_offset(3),
        ]

    def get_program_start_time_offset_type(self, start_index):
        """Retrieve program start time offset type ('midnight', 'sunset', or 'sunrise')"""
        if not 0 <= start_index <= 3:
            raise IndexError("start_index must be between 0 and 3")

        start_times = self._get_variable(3)
        return self._get_offset_type(start_times, start_index)

    @property
    def program_start_time_offset_types(self):
        """Retrieve list of program start time offset types ('midnight', 'sunset', or 'sunrise')"""
        return [
            self.get_program_start_time_offset_type(0),
            self.get_program_start_time_offset_type(1),
            self.get_program_start_time_offset_type(2),
            self.get_program_start_time_offset_type(3),
        ]

    @property
    def program_start_repeat_count(self):
        """Retrieve program start repeat count"""
        return self._get_variable(3)[1]

    @property
    def program_start_repeat_interval(self):
        """Retrieve program start repeat interval in minutes"""
        return self._get_variable(3)[2]

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

    @property
    def starting_in_days(self):
        """Retrieve days0 (starting in days in Interval mode)"""
        return self._get_variable(1)

    @property
    def interval_days(self):
        """Retrieve days1 (interval days in Interval mode)"""
        return self._get_variable(2)

    def get_weekday_enabled(self, weekday):
        """Retrieve program weekday enabled state ('Monday', 'Tuesday', etc.)"""
        weekday_bits = self._get_variable(1)
        return self._is_set(weekday_bits, WEEKDAYS.index(weekday))
