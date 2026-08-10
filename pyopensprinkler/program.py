"""Program module handling /program/ API calls."""

import json
import logging

from pyopensprinkler.const import (
    SCHEDULE_START_TIME_FIXED,
    SCHEDULE_START_TIME_FIXED_CODE,
    SCHEDULE_START_TIME_OFFSET_DISABLED,
    SCHEDULE_START_TIME_OFFSET_MIDNIGHT,
    SCHEDULE_START_TIME_OFFSET_SUNRISE,
    SCHEDULE_START_TIME_OFFSET_SUNSET,
    SCHEDULE_START_TIME_REPEATING,
    SCHEDULE_START_TIME_REPEATING_CODE,
    SCHEDULE_TYPE_INTERVAL_DAY,
    SCHEDULE_TYPE_INTERVAL_DAY_CODE,
    SCHEDULE_TYPE_MONTHLY,
    SCHEDULE_TYPE_MONTHLY_CODE,
    SCHEDULE_TYPE_SINGLE_RUN,
    SCHEDULE_TYPE_SINGLE_RUN_CODE,
    SCHEDULE_TYPE_WEEKLY,
    SCHEDULE_TYPE_WEEKLY_CODE,
    START_TIME_MINUTES_MASK,
    START_TIME_SIGN_BIT,
    START_TIME_SUNRISE_BIT,
    START_TIME_SUNSET_BIT,
    WEEKDAYS,
)

from .exceptions import FirmwareNotSupportedError
from .utils import _is_new_feature_supported

_LOGGER = logging.getLogger(__name__)


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

    async def _manual_run(self, uwt=None, qo=None):
        """Run program"""
        if uwt is None:
            uwt = self.use_weather_adjustments
        params = {"pid": self._index, "uwt": int(uwt)}
        if qo is not None:
            params["qo"] = qo
        content = await self._controller.request("/mp", params)
        return content["result"]

    def _get_data_flag_bits(self):
        return list(
            reversed([int(x) for x in list("{0:08b}".format(self._get_variable(0)))])
        )

    def _bits_to_int(self, bits):
        return int("".join(map(str, list(reversed(bits)))), 2)

    def _format_program_data(self, dlist):
        """Convert from /jp (Get) to /cp (Change) message format"""
        # Move program name from 'v' to 'name' parameter.
        name = dlist.pop(5)

        # Move Date-range tuple from 'v' to 'from' and 'to' parameters, if present (since v2.2.0(1)).
        if len(dlist) >= 6:
            date_range = dlist.pop(5)
        else:
            date_range = [
                0,
                33,
                415,
            ]  # Jan 1 to Dec 31 (default range, but won't be used)

        # Remove spaces.
        v = json.dumps(dlist).replace(" ", "")

        params = {"v": v, "name": name, "from": date_range[1], "to": date_range[2]}
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

    def _is_valid_date(self, month, day):
        """Check if month and day are valid"""
        if not 1 <= month <= 12:
            return False
        if not 1 <= day <= 31:
            return False
        if month in [4, 6, 9, 11] and day > 30:
            return False
        if month == 2 and day > 29:
            return False
        return True

    async def enable(self):
        """Enable the program.

        Returns:
            API result code (1 = success).
        """
        return await self.set_enabled(True)

    async def disable(self):
        """Disable the program.

        Returns:
            API result code (1 = success).
        """
        return await self.set_enabled(False)

    async def set_enabled(self, value):
        """Set the program enabled state.

        Args:
            value: True to enable, False to disable.

        Returns:
            API result code (1 = success).
        """
        if value:
            return await self._set_variable("en", 1)
        else:
            return await self._set_variable("en", 0)

    async def run(self, uwt=None, qo=None):
        """Run the program manually.

        Args:
            uwt: Optional weather adjustment flag (0/1); defaults to the
                program's ``use_weather_adjustments`` setting.
            qo: Optional queue option (0 = append to queue, 1 = insert
                ahead of queue, 2 = replace queue).

        Returns:
            API result code (1 = success).
        """
        return await self._manual_run(uwt, qo)

    async def set_name(self, name):
        """Set the program name.

        Args:
            name: New program name.

        Returns:
            API result code (1 = success).
        """
        dlist = self._get_program_data().copy()
        dlist[5] = name
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_use_weather_adjustments(self, value):
        """Set whether the program uses weather (water level) adjustments.

        Args:
            value: Truthy to enable weather adjustments.

        Returns:
            API result code (1 = success).
        """
        return await self._set_variable("uwt", int(value))

    async def set_odd_even_restriction(self, value):
        """Set the odd/even day restriction.

        Args:
            value: 0 = none, 1 = odd days, 2 = even days.

        Returns:
            API result code (1 = success).

        Raises:
            ValueError: If value is outside 0-2.
        """
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
        """Set the program schedule type.

        Changing the type resets days0/days1 to defaults since their
        meaning depends on the schedule type.

        Args:
            value: 0 = weekly, 1 = single run, 2 = monthly,
                3 = interval day. Single run and monthly require
                firmware v2.2.1(1).

        Returns:
            API result code (1 = success).

        Raises:
            FirmwareNotSupportedError: If value is single run or monthly
                and the firmware is older than v2.2.1(1).
            ValueError: If value is outside 0-3.
        """
        if value in [
            SCHEDULE_TYPE_SINGLE_RUN_CODE,
            SCHEDULE_TYPE_MONTHLY_CODE,
        ] and not _is_new_feature_supported(self._controller, 221, 1):
            raise FirmwareNotSupportedError("Feature requires firmware v2.2.1(1)")

        if not 0 <= value <= 3:
            raise ValueError("Value must be between 0 and 3")

        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()

        if value == SCHEDULE_TYPE_WEEKLY_CODE:
            bits[4] = 0
            bits[5] = 0

        if value == SCHEDULE_TYPE_SINGLE_RUN_CODE:
            bits[4] = 1
            bits[5] = 0

        if value == SCHEDULE_TYPE_MONTHLY_CODE:
            bits[4] = 0
            bits[5] = 1

        if value == SCHEDULE_TYPE_INTERVAL_DAY_CODE:
            bits[4] = 1
            bits[5] = 1

        # If changing type, data in days0-1 becomes meaningless, so set to default.
        if dlist[0] != self._bits_to_int(bits):
            dlist[1] = 0
            dlist[2] = (
                1 if value == SCHEDULE_TYPE_INTERVAL_DAY_CODE else 0
            )  # Interval day must be >= 1
            dlist[0] = self._bits_to_int(bits)
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_start_time_type(self, value):
        """Set the start time type.

        Changing the type resets start1-start3 to defaults since their
        meaning depends on the start time type.

        Args:
            value: 0 = repeating, 1 = fixed.

        Returns:
            API result code (1 = success).

        Raises:
            ValueError: If value is not 0 or 1.
        """
        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()

        if value < 0 or value > 1:
            raise ValueError("Value must be 0 or 1")

        if value == SCHEDULE_START_TIME_REPEATING_CODE:
            bits[6] = 0

        if value == SCHEDULE_START_TIME_FIXED_CODE:
            bits[6] = 1

        # If changing type, data in start1-3 becomes meaningless, so set to default.
        if dlist[0] != self._bits_to_int(bits):
            dlist[3][1] = 0 if value == SCHEDULE_START_TIME_REPEATING_CODE else -1
            dlist[3][2] = 0 if value == SCHEDULE_START_TIME_REPEATING_CODE else -1
            dlist[3][3] = 0 if value == SCHEDULE_START_TIME_REPEATING_CODE else -1
            dlist[0] = self._bits_to_int(bits)
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_time(self, start_index, start_time):
        """Set a program start time.

        Args:
            start_index: Which start time to set (0-3).
            start_time: Encoded start time value (minutes from midnight
                for simple start times).

        Returns:
            API result code (1 = success).

        Raises:
            IndexError: If start_index is outside 0-3.
        """
        if not 0 <= start_index <= 3:
            raise IndexError("start_index must be between 0 and 3")
        dlist = self._get_program_data().copy()
        dlist[3][start_index] = start_time
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_times(self, start_times):
        """Set all four program start times at once.

        Args:
            start_times: List of 4 encoded start time values for
                start0-start3.

        Returns:
            API result code (1 = success).
        """
        dlist = self._get_program_data().copy()
        dlist[3] = start_times
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_time_offset(self, start_index, start_time_offset):
        """Set a program start time offset in minutes.

        Keeps the current offset type; a disabled start time is assumed
        to become midnight-relative.

        Args:
            start_index: Which start time to update (0-3).
            start_time_offset: Offset in minutes (negative for before).

        Returns:
            API result code (1 = success).

        Raises:
            IndexError: If start_index is outside 0-3.
            RuntimeError: If start_index > 0 and the start time type is
                'repeating' (only start0 exists in that mode).
        """
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
        """Set a program start time offset type.

        Resets the offset minutes to 0.

        Args:
            start_index: Which start time to update (0-3).
            start_time_offset_type: One of 'disabled', 'midnight',
                'sunset', or 'sunrise'.

        Returns:
            API result code (1 = success).

        Raises:
            IndexError: If start_index is outside 0-3.
            RuntimeError: If start_index > 0 and the start time type is
                'repeating' (only start0 exists in that mode).
            ValueError: If start_time_offset_type is not a valid option.
        """
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
        """Set the program start repeat count.

        Args:
            repeat_count: Number of times to repeat the start.

        Returns:
            API result code (1 = success).

        Raises:
            RuntimeError: If the start time type is 'fixed'.
        """
        if self.start_time_type == 1:
            raise RuntimeError(
                "Cannot update repeat count when start time type is 'fixed'"
            )

        dlist = self._get_program_data().copy()
        dlist[3][1] = repeat_count
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_program_start_repeat_interval(self, repeat_minutes):
        """Set the program start repeat interval.

        Args:
            repeat_minutes: Interval between repeats in minutes.

        Returns:
            API result code (1 = success).

        Raises:
            RuntimeError: If the start time type is 'fixed'.
        """
        if self.start_time_type == 1:
            raise RuntimeError(
                "Cannot update repeat count when start time type is 'fixed'"
            )

        dlist = self._get_program_data().copy()
        dlist[3][2] = repeat_minutes
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_weekday_enabled(self, weekday, enabled):
        """Set whether the program runs on a given weekday.

        Args:
            weekday: Weekday name ('Monday', 'Tuesday', etc.).
            enabled: True to run on that weekday, False to skip it.

        Returns:
            API result code (1 = success).

        Raises:
            RuntimeError: If the schedule type is not 'weekly'.
        """
        if self.program_schedule_type != 0:
            raise RuntimeError(
                "Cannot update Weekly schedule when schedule type is not 'Weekday'"
            )

        dlist = self._get_program_data().copy()
        dlist[1] = self._bit_set(dlist[1], WEEKDAYS.index(weekday), enabled)
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_station_duration(self, station_index, duration):
        """Set the run duration of one station in the program.

        Args:
            station_index: 0-based station index.
            duration: Run duration in seconds (0 to skip the station).

        Returns:
            API result code (1 = success).
        """
        dlist = self._get_program_data().copy()
        dlist[4][station_index] = duration
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_station_durations(self, durations):
        """Set the run durations of all stations in the program.

        Args:
            durations: List of run durations in seconds, one entry per
                station (0 to skip a station).

        Returns:
            API result code (1 = success).
        """
        dlist = self._get_program_data().copy()
        dlist[4] = durations
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_days0(self, value):
        """Set days0 directly (meaning depends on the schedule type).

        Args:
            value: Raw days0 value.

        Returns:
            API result code (1 = success).
        """
        dlist = self._get_program_data().copy()
        dlist[1] = value
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_days1(self, value):
        """Set days1 directly (meaning depends on the schedule type).

        Args:
            value: Raw days1 value.

        Returns:
            API result code (1 = success).
        """
        dlist = self._get_program_data().copy()
        dlist[2] = value
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_starting_in_days(self, value):
        """Set 'starting in days' (days0 in Interval-Day mode).

        Args:
            value: Number of days until the program starts.

        Returns:
            API result code (1 = success).

        Raises:
            RuntimeError: If the schedule type is not 'Interval-Day'.
        """
        if self.program_schedule_type != SCHEDULE_TYPE_INTERVAL_DAY_CODE:
            raise RuntimeError(
                "Cannot update Starting In Days when schedule type is not 'Interval-Day'"
            )

        dlist = self._get_program_data().copy()
        dlist[1] = value
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_interval_days(self, value):
        """Set the interval in days (days1 in Interval-Day mode).

        Args:
            value: Interval in days (must be >= 1).

        Returns:
            API result code (1 = success).

        Raises:
            RuntimeError: If the schedule type is not 'Interval-Day'.
        """
        if self.program_schedule_type != SCHEDULE_TYPE_INTERVAL_DAY_CODE:
            raise RuntimeError(
                "Cannot update Interval Days when schedule type is not 'Interval-Day'"
            )

        dlist = self._get_program_data().copy()
        dlist[2] = value
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_monthly_day(self, day_of_month):
        """Set the day of month to run on (days0 in Monthly mode).

        Args:
            day_of_month: Day of month, 0-31.

        Returns:
            API result code (1 = success).

        Raises:
            RuntimeError: If the schedule type is not 'Monthly'.
            ValueError: If day_of_month is outside 0-31.
        """
        if self.program_schedule_type != SCHEDULE_TYPE_MONTHLY_CODE:
            raise RuntimeError(
                "Cannot update Monthly Day when schedule type is not 'Monthly'"
            )

        if not 0 <= day_of_month <= 31:
            raise ValueError("Value must be between 0 and 31")

        dlist = self._get_program_data().copy()
        dlist[1] = day_of_month
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_single_run_day(self, days_since_epoch):
        """Set the single run day (days0/days1 in Single-Run mode).

        Args:
            days_since_epoch: Run day expressed as days since the epoch,
                0-65535.

        Returns:
            API result code (1 = success).

        Raises:
            RuntimeError: If the schedule type is not 'Single-run'.
            ValueError: If days_since_epoch is outside 0-65535.
        """
        if self.program_schedule_type != SCHEDULE_TYPE_SINGLE_RUN_CODE:
            raise RuntimeError(
                "Cannot update Single Run Day when schedule type is not 'Single-run'"
            )

        if not 0 <= days_since_epoch <= 65535:
            raise ValueError("Value must be between 0 and 65535")

        dlist = self._get_program_data().copy()
        dlist[1] = (days_since_epoch >> 8) & 0xFF
        dlist[2] = days_since_epoch & 0xFF
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_date_range_from(self, start_month: int, start_day: int):
        """Set the program date range start date.

        Args:
            start_month: Start month (1-12).
            start_day: Start day of month (1-31).

        Returns:
            API result code (1 = success).

        Raises:
            FirmwareNotSupportedError: If the firmware is older than
                v2.2.0(1).
            ValueError: If the date is invalid.
        """
        if not _is_new_feature_supported(self._controller, 220, 1):
            raise FirmwareNotSupportedError("Feature requires firmware v2.2.0(1)")

        if not self._is_valid_date(start_month, start_day):
            raise ValueError("Invalid date")

        dlist = self._get_program_data().copy()
        dlist[6][1] = (start_month << 5) + start_day
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_date_range_to(self, end_month: int, end_day: int):
        """Set the program date range end date.

        Args:
            end_month: End month (1-12).
            end_day: End day of month (1-31).

        Returns:
            API result code (1 = success).

        Raises:
            FirmwareNotSupportedError: If the firmware is older than
                v2.2.0(1).
            ValueError: If the date is invalid.
        """
        if not _is_new_feature_supported(self._controller, 220, 1):
            raise FirmwareNotSupportedError("Feature requires firmware v2.2.0(1)")

        if not self._is_valid_date(end_month, end_day):
            raise ValueError("Invalid date")

        dlist = self._get_program_data().copy()
        dlist[6][2] = (end_month << 5) + end_day
        params = self._format_program_data(dlist)
        return await self._set_variables(params)

    async def set_date_range_flag(self, enabled: bool):
        """Enable or disable the program date range restriction.

        Args:
            enabled: 1 to enable, 0 to disable.

        Returns:
            API result code (1 = success).

        Raises:
            FirmwareNotSupportedError: If the firmware is older than
                v2.2.0(1).
            ValueError: If enabled is not 0 or 1.
        """
        if not _is_new_feature_supported(self._controller, 220, 1):
            raise FirmwareNotSupportedError("Feature requires firmware v2.2.0(1)")

        if enabled < 0 or enabled > 1:
            raise ValueError("Enabled must be 0 or 1")

        # Set date range bit in flag field
        dlist = self._get_program_data().copy()
        bits = self._get_data_flag_bits()
        bits[7] = enabled
        dlist[0] = self._bits_to_int(bits)

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
        """Whether any station is currently running this program."""
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
        """Odd/even restriction name ('odd_days' or 'even_days'),
        or None if unrestricted."""
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
        """Program schedule type name ('weekday', 'single-run',
        'monthly', or 'interval_day'), or None."""
        value = self.program_schedule_type

        if value == SCHEDULE_TYPE_WEEKLY_CODE:
            return SCHEDULE_TYPE_WEEKLY

        if value == SCHEDULE_TYPE_SINGLE_RUN_CODE:
            return SCHEDULE_TYPE_SINGLE_RUN

        if value == SCHEDULE_TYPE_MONTHLY_CODE:
            return SCHEDULE_TYPE_MONTHLY

        if value == SCHEDULE_TYPE_INTERVAL_DAY_CODE:
            return SCHEDULE_TYPE_INTERVAL_DAY

        return None

    @property
    def start_time_type(self):
        """Start time type integer (0 = repeating, 1 = fixed)."""
        return self._get_data_flag_bits()[6]

    @property
    def start_time_type_name(self):
        """Start time type name ('repeating' or 'fixed_time'), or None."""
        value = self.start_time_type

        if value == 0:
            return SCHEDULE_START_TIME_REPEATING

        if value == 1:
            return SCHEDULE_START_TIME_FIXED

    @property
    def date_range_enabled(self):
        """Whether the date range restriction is enabled.

        Returns 0 on firmware older than v2.2.0(1).
        """
        if not _is_new_feature_supported(self._controller, 220, 1):
            return 0
        else:
            return self._get_data_flag_bits()[7]

    @property
    def date_range_from(self):
        """Date range start as a (month, day) tuple.

        Returns (1, 1) on firmware older than v2.2.0(1).
        """
        if not _is_new_feature_supported(self._controller, 220, 1):
            return 1, 1  # Jan 1 default
        else:
            date_range = self._get_variable(6)
            month = date_range[1] >> 5
            day = date_range[1] & 0x1F
            return month, day

    @property
    def date_range_to(self):
        """Date range end as a (month, day) tuple.

        Returns (12, 31) on firmware older than v2.2.0(1).
        """
        if not _is_new_feature_supported(self._controller, 220, 1):
            return 12, 31  # Dec 31 default
        else:
            date_range = self._get_variable(6)
            month = date_range[2] >> 5
            day = date_range[2] & 0x1F
            return month, day

    def get_program_start_time(self, start_index):
        """Retrieve a program start time as an encoded value.

        Args:
            start_index: Which start time to retrieve (0-3).

        Returns:
            Encoded start time value (minutes from midnight for simple
            start times).
        """
        return self._get_variable(3)[start_index]

    @property
    def program_start_times(self):
        """Retrieve program start times in list of encoded values"""
        return self._get_variable(3)

    def get_program_start_time_offset(self, start_index):
        """Retrieve a program start time offset in minutes.

        Args:
            start_index: Which start time to retrieve (0-3).

        Returns:
            Offset in minutes relative to the offset type.

        Raises:
            IndexError: If start_index is outside 0-3.
        """
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
        """Retrieve a program start time offset type.

        Args:
            start_index: Which start time to retrieve (0-3).

        Returns:
            One of 'disabled', 'midnight', 'sunset', or 'sunrise'; None
            for start1-3 when the start time type is 'repeating'.

        Raises:
            IndexError: If start_index is outside 0-3.
        """
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
        """Retrieve days0 (meaning depends on the schedule type)"""
        return self._get_variable(1)

    @property
    def days1(self):
        """Retrieve days1 (meaning depends on the schedule type)"""
        return self._get_variable(2)

    @property
    def starting_in_days(self):
        """Retrieve days0 (starting in days in Interval mode)"""
        return self._get_variable(1)

    @property
    def interval_days(self):
        """Retrieve days1 (interval days in Interval mode)"""
        return self._get_variable(2)

    @property
    def monthly_day(self):
        """Retrieve days0 (day of month in Monthly mode)"""
        return self._get_variable(1)

    @property
    def single_run_day(self):
        """Retrieve days0 and days1 as 16-bit unsigned integer (days since epoch time in Single-Run mode)"""
        return self._get_variable(2) + (self._get_variable(1) << 8)

    def get_weekday_enabled(self, weekday):
        """Retrieve whether the program runs on a given weekday.

        Args:
            weekday: Weekday name ('Monday', 'Tuesday', etc.).

        Returns:
            True if the program runs on that weekday.
        """
        weekday_bits = self._get_variable(1)
        return self._is_set(weekday_bits, WEEKDAYS.index(weekday))
