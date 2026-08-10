"""Station module handling /station/ API calls."""

import math

from pyopensprinkler.const import (
    STATION_STATUS_IDLE,
    STATION_STATUS_MANUAL,
    STATION_STATUS_MASTER_ENGAGED,
    STATION_STATUS_ONCE_PROGRAM,
    STATION_STATUS_PROGRAM,
    STATION_STATUS_WAITING,
    STATION_TYPE_STANDARD,
)

from .exceptions import FirmwareNotSupportedError
from .utils import _is_new_feature_supported, _is_removed_feature_supported


class Station(object):
    """Station class with /station/ API calls."""

    def __init__(self, controller, index):
        """Station class initializer."""
        self._controller = controller
        self._index = index

    def _get_status_variable(self, statusIndex):
        """
        Retrieve station variable

        Program status data: each element is a 3-field array that stores the [pid,rem,start] of a station, where
        pid is the program index (0 means none), rem is the remaining water time (in seconds), start is the start time.
        If a station is not running (sbit is 0) but has a non-zero pid, that means the station is in the queue
        waiting to run.
        """
        return self._controller._state["settings"]["ps"][self._index][statusIndex]

    async def _manual_run(self, params=None):
        """Manual station run"""
        if params is None:
            params = {}
        params["sid"] = self._index
        content = await self._controller.request("/cm", params)
        return content["result"]

    async def _set_attribute(self, attribute, value):
        return await self._set_attributes({attribute: value})

    async def _set_attributes(self, params=None):
        if params is None:
            params = {}

        content = await self._controller.request("/cs", params)
        return content["result"]

    def _bit_check(self, bit_property):
        # [254, 255, 255]
        # 254 = all but first station in the first block of 8 have master1 enabled
        # each entry is for next block of 8 stations
        bits = self._controller._state["stations"][bit_property]
        bank = math.floor(self._index / 8)
        bits = list(reversed([int(x) for x in list("{0:08b}".format(bits[bank]))]))
        position = self._index % 8

        return bool(bits[position])

    async def _bit_set(self, bit_property, bit_update_name, value):
        bit_list = self._controller._state["stations"][bit_property]
        bank = math.floor(self._index / 8)
        bits = list(reversed([int(x) for x in list("{0:08b}".format(bit_list[bank]))]))
        position = self._index % 8
        value = int(value)
        bits[position] = value
        bits = list(reversed(bits))
        bits = "".join(map(str, bits))
        bits = int(bits, 2)
        bit_list[bank] = bits
        self._controller._state["stations"][bit_property] = bit_list
        return await self._set_attribute(bit_update_name + str(bank), bits)

    async def run(self, seconds=None, qo=None):
        """Run the station manually.

        Args:
            seconds: Run duration in seconds (default 60).
            qo: Optional queue option (firmware 2.2.1+); False appends to
                the queue, True inserts ahead of the queue.

        Returns:
            API result code (1 = success).
        """
        if seconds is None:
            seconds = 60
        params = {"en": 1, "t": seconds}
        if qo is not None:
            params["qo"] = qo
        return await self._manual_run(params)

    async def stop(self, ssta=None):
        """Stop the station.

        Args:
            ssta: Optional shift flag (firmware 2.2.1+); True shifts the
                remaining stations in the station's group forward.

        Returns:
            API result code (1 = success).
        """
        params = {"en": 0}
        if ssta is not None:
            params["ssta"] = int(ssta)
        return await self._manual_run(params)

    async def toggle(self):
        """Toggle the station: stop it if running, otherwise run it for
        the default duration.

        Returns:
            API result code (1 = success).
        """
        if self.is_running:
            return await self.stop()
        else:
            return await self.run()

    async def set_name(self, name):
        """Set the station name.

        Args:
            name: New station name.

        Returns:
            API result code (1 = success).
        """
        return await self._set_attribute("s" + str(self.index), name)

    async def enable(self):
        """Enable the station.

        Returns:
            API result code (1 = success).
        """
        return await self.set_enabled(True)

    async def disable(self):
        """Disable the station.

        Returns:
            API result code (1 = success).
        """
        return await self.set_enabled(False)

    async def set_enabled(self, value):
        """Set the station enabled state.

        Args:
            value: True to enable, False to disable.

        Returns:
            API result code (1 = success).
        """
        bit_property = "stn_dis"
        bit_update_name = "d"
        if value:
            return await self._bit_set(bit_property, bit_update_name, False)
        else:
            return await self._bit_set(bit_property, bit_update_name, True)

    async def set_master_1_operation_enabled(self, value):
        """Set whether the station activates master 1.

        Args:
            value: True to engage master 1 when the station runs.

        Returns:
            API result code (1 = success).
        """
        bit_property = "masop"
        bit_update_name = "m"
        if value:
            return await self._bit_set(bit_property, bit_update_name, True)
        else:
            return await self._bit_set(bit_property, bit_update_name, False)

    async def set_master_2_operation_enabled(self, value):
        """Set whether the station activates master 2.

        Args:
            value: True to engage master 2 when the station runs.

        Returns:
            API result code (1 = success).
        """
        bit_property = "masop2"
        bit_update_name = "n"
        if value:
            return await self._bit_set(bit_property, bit_update_name, True)
        else:
            return await self._bit_set(bit_property, bit_update_name, False)

    async def set_group(self, value):
        """Set the station group.

        Args:
            value: Group id, 0-255.

        Returns:
            API result code (1 = success).

        Raises:
            FirmwareNotSupportedError: If the firmware is older than
                v2.2.0(1).
            ValueError: If value is outside 0-255.
        """
        if not _is_new_feature_supported(self._controller, 220, 1):
            raise FirmwareNotSupportedError("Feature requires firmware v2.2.0(1)")

        if not 0 <= value <= 255:
            raise ValueError("Value must be between 0 and 255")
        return await self._set_attribute("g" + str(self.index), value)

    async def set_rain_delay_ignored(self, value):
        """Set whether the station ignores rain delay.

        Args:
            value: True to run even during a rain delay.

        Returns:
            API result code (1 = success).
        """
        bit_property = "ignore_rain"
        bit_update_name = "i"
        if value:
            return await self._bit_set(bit_property, bit_update_name, True)
        else:
            return await self._bit_set(bit_property, bit_update_name, False)

    async def set_sensor_1_ignored(self, value):
        """Set whether the station ignores sensor 1.

        Args:
            value: True to run even when sensor 1 is active.

        Returns:
            API result code (1 = success).
        """
        bit_property = "ignore_sn1"
        bit_update_name = "j"
        if value:
            return await self._bit_set(bit_property, bit_update_name, True)
        else:
            return await self._bit_set(bit_property, bit_update_name, False)

    async def set_sensor_2_ignored(self, value):
        """Set whether the station ignores sensor 2.

        Args:
            value: True to run even when sensor 2 is active.

        Returns:
            API result code (1 = success).
        """
        bit_property = "ignore_sn2"
        bit_update_name = "k"
        if value:
            return await self._bit_set(bit_property, bit_update_name, True)
        else:
            return await self._bit_set(bit_property, bit_update_name, False)

    async def set_sequential_operation(self, value):
        """Set whether the station runs sequentially (vs. in parallel).

        Args:
            value: True for sequential operation.

        Returns:
            API result code (1 = success).

        Raises:
            FirmwareNotSupportedError: If the firmware is v2.2.1(0) or
                newer (feature removed).
        """
        if not _is_removed_feature_supported(self._controller, 221, 0):
            raise FirmwareNotSupportedError("Feature removed in v2.2.1(0)")

        bit_property = "stn_seq"
        bit_update_name = "q"
        if value:
            return await self._bit_set(bit_property, bit_update_name, True)
        else:
            return await self._bit_set(bit_property, bit_update_name, False)

    @property
    def name(self):
        """Station name"""
        return self._controller._state["stations"]["snames"][self._index]

    @property
    def index(self):
        """Station index"""
        return self._index

    @property
    def is_running(self):
        """Whether the station is currently running."""
        return bool(self._controller._state["status"]["sn"][self._index])

    @property
    def is_master(self):
        """Whether the station is configured as master 1 or master 2."""
        # stored in controller 1 indexed vs 0 indexed
        station_id = self.index + 1
        return (
            self._controller.master_station_1 == station_id
            or self._controller.master_station_2 == station_id
        )

    @property
    def running_program_id(self):
        """ID of the program running this station (1-based; 0 means
        none)."""
        return self._get_status_variable(0)

    @property
    def seconds_remaining(self):
        """Remaining run time in seconds."""
        return self._get_status_variable(1)

    @property
    def start_time(self):
        """Start time as a UTC epoch timestamp."""
        return self._controller._timestamp_to_utc(self._get_status_variable(2))

    @property
    def end_time(self):
        """End time as a UTC epoch timestamp (0 if not started)."""
        if self.start_time == 0:
            return 0
        return (
            max(self.start_time, self._controller.device_time) + self.seconds_remaining
        )

    @property
    def max_name_length(self):
        """Maximum supported station name length."""
        return self._controller._state["stations"]["maxlen"]

    @property
    def master_1_operation_enabled(self):
        """Whether the station activates master 1."""
        return self._bit_check("masop")

    @property
    def master_2_operation_enabled(self):
        """Whether the station activates master 2."""
        return self._bit_check("masop2")

    @property
    def group(self):
        """Station group id.

        Raises:
            FirmwareNotSupportedError: If the firmware is older than
                v2.2.0(1).
        """
        if not _is_new_feature_supported(self._controller, 220, 1):
            raise FirmwareNotSupportedError("Feature requires firmware v2.2.0(1)")
        return self._controller._state["stations"]["stn_grp"][self._index]

    @property
    def rain_delay_ignored(self):
        """Whether the station ignores rain delay."""
        return self._bit_check("ignore_rain")

    @property
    def sensor_1_ignored(self):
        """Whether the station ignores sensor 1."""
        return self._bit_check("ignore_sn1")

    @property
    def sensor_2_ignored(self):
        """Whether the station ignores sensor 2."""
        return self._bit_check("ignore_sn2")

    @property
    def enabled(self):
        """Whether the station is enabled."""
        return not self._bit_check("stn_dis")

    @property
    def sequential_operation(self):
        """Whether the station runs sequentially (vs. in parallel).

        Raises:
            FirmwareNotSupportedError: If the firmware is v2.2.1(0) or
                newer (feature removed).
        """
        if not _is_removed_feature_supported(self._controller, 221, 0):
            raise FirmwareNotSupportedError("Feature removed in v2.2.1(0)")

        return self._bit_check("stn_seq")

    @property
    def special(self):
        """Whether the station is a special station (e.g. RF, remote)."""
        return self._bit_check("stn_spe")

    @property
    def station_type(self):
        """Station type ('standard'), or None for special stations."""
        if not self.special:
            return STATION_TYPE_STANDARD

        # TODO: fetch the /je endpoint and return as appropriate

    # TODO: implement setting station options /cs endpoint

    @property
    def status(self):
        """Station status name: 'idle', 'manual', 'master_engaged',
        'once_program', 'program', or 'waiting'."""
        is_running = self.is_running
        pid = self.running_program_id

        if is_running:
            if pid == 99:
                state = STATION_STATUS_MANUAL
            elif pid == 254:
                state = STATION_STATUS_ONCE_PROGRAM
            elif pid == 0:
                if self.is_master:
                    state = STATION_STATUS_MASTER_ENGAGED
                else:
                    state = STATION_STATUS_IDLE
            else:
                state = STATION_STATUS_PROGRAM
        else:
            if pid > 0:
                state = STATION_STATUS_WAITING
            else:
                state = STATION_STATUS_IDLE

        return state
