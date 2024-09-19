import asyncio

import pytest
from const import FIRMWARE_VERSION


@pytest.fixture
async def program(controller):
    await controller.create_program("test program")
    program = controller.programs[0]
    yield program
    await controller.delete_program(0)


class TestProgram:
    @pytest.mark.asyncio
    async def test_index(self, controller, program):
        assert controller.programs[0].index == 0
        assert program.index == 0

    @pytest.mark.asyncio
    async def test_odd_even_restriction(self, controller, program):
        assert program.odd_even_restriction == 0
        assert program.odd_even_restriction_name is None

        await program.set_odd_even_restriction(1)
        assert program.odd_even_restriction == 1
        assert program.odd_even_restriction_name == "odd_days"

        await program.set_odd_even_restriction(2)
        assert program.odd_even_restriction == 2
        assert program.odd_even_restriction_name == "even_days"

        await program.set_odd_even_restriction(0)
        assert program.odd_even_restriction == 0
        assert program.odd_even_restriction_name is None

    @pytest.mark.skipif(
        FIRMWARE_VERSION <= 216, reason="only for version 217 and above"
    )
    @pytest.mark.asyncio
    async def test_program_manual_run(self, controller, program):
        await program.set_station_duration(0, 25)
        # controller.set_water_level only works from version 219
        if FIRMWARE_VERSION >= 219:
            await controller.set_water_level(20)
        else:
            await controller._set_option("o23", 20)

        await program._manual_run()
        await asyncio.sleep(1)
        await controller.refresh()
        assert (
            controller.stations[0].end_time - controller.stations[0].start_time
        ) == 25

        await program._manual_run(1)
        await asyncio.sleep(1)
        await controller.refresh()
        assert (
            controller.stations[0].end_time - controller.stations[0].start_time
        ) == 5

        await program._manual_run(0)
        await asyncio.sleep(1)
        await controller.refresh()
        assert (
            controller.stations[0].end_time - controller.stations[0].start_time
        ) == 25

    @pytest.mark.skipif(
        FIRMWARE_VERSION <= 216, reason="only for version 217 and above"
    )
    @pytest.mark.asyncio
    async def test_program_run(self, controller, program):
        await program.set_station_duration(0, 25)
        # controller.set_water_level only works from version 219
        if FIRMWARE_VERSION >= 219:
            await controller.set_water_level(20)
        else:
            await controller._set_option("o23", 20)

        await program.run()
        await asyncio.sleep(1)
        await controller.refresh()
        assert (
            controller.stations[0].end_time - controller.stations[0].start_time
        ) == 25

        await program.run(1)
        await asyncio.sleep(1)
        await controller.refresh()
        assert (
            controller.stations[0].end_time - controller.stations[0].start_time
        ) == 5

        await program.run(0)
        await asyncio.sleep(1)
        await controller.refresh()
        assert (
            controller.stations[0].end_time - controller.stations[0].start_time
        ) == 25

    @pytest.mark.asyncio
    async def test_program_schedule_type(self, controller, program):
        assert program.program_schedule_type == 0
        assert program.program_schedule_type_name == "weekday"

        await program.set_program_schedule_type(3)
        assert program.program_schedule_type == 3
        assert program.program_schedule_type_name == "interval_day"

        await program.set_program_schedule_type(0)
        assert program.program_schedule_type == 0
        assert program.program_schedule_type_name == "weekday"

    @pytest.mark.asyncio
    async def test_start_time_type(self, controller, program):
        assert program.start_time_type == 0
        assert program.start_time_type_name == "repeating"

        await program.set_start_time_type(1)
        assert program.start_time_type == 1
        assert program.start_time_type_name == "fixed_time"

        await program.set_start_time_type(0)
        assert program.start_time_type == 0
        assert program.start_time_type_name == "repeating"

    @pytest.mark.asyncio
    async def test_set_name(self, controller, program):
        await program.set_name("Test")
        assert program.name == "Test"

    @pytest.mark.asyncio
    async def test_set_program_start_time(self, controller, program):
        await program.set_program_start_time(0, 360)
        assert program.program_start_times[0] == 360

    @pytest.mark.asyncio
    async def test_set_program_start_time_3(self, controller, program):
        await program.set_program_start_time(3, 120)
        assert program.program_start_times[3] == 120

    @pytest.mark.asyncio
    async def test_set_program_start_time_offset_type(self, controller, program):
        await program.set_program_start_time_offset_type(0, "sunset")
        await program.set_program_start_time_offset(0, -60)
        assert program.get_program_start_time_offset_type(0) == "sunset"
        assert program.get_program_start_time_offset(0) == -60

    @pytest.mark.asyncio
    async def test_set_program_start_time_offset(self, controller, program):
        await program.set_start_time_type(1)
        await program.set_program_start_time_offset_type(1, "midnight")
        await program.set_program_start_time_offset(1, 30)
        assert program.start_time_type == 1
        assert program.get_program_start_time_offset_type(1) == "midnight"
        assert program.get_program_start_time_offset(1) == 30

    @pytest.mark.asyncio
    async def test_set_program_start_repeat_count(self, controller, program):
        await program.set_start_time_type(0)
        await program.set_program_start_repeat_count(2)
        assert program.program_start_repeat_count == 2

    @pytest.mark.asyncio
    async def test_set_program_start_repeat_interval(self, controller, program):
        await program.set_start_time_type(0)
        await program.set_program_start_repeat_interval(60)
        assert program.program_start_repeat_interval == 60

    @pytest.mark.asyncio
    async def test_set_station_duration(self, controller, program):
        await program.set_station_duration(0, 1800)
        assert program.station_durations[0] == 1800

    @pytest.mark.asyncio
    async def test_set_days0(self, controller, program):
        await program.set_days0(1)
        assert program.days0 == 1

    @pytest.mark.asyncio
    async def test_set_days1(self, controller, program):
        await program.set_days1(3)
        assert program.days1 == 3

    @pytest.mark.asyncio
    async def test_set_weekday_enabled(self, controller, program):
        await program.set_program_schedule_type(0)
        await program.set_weekday_enabled("Monday", True)
        assert program.program_schedule_type_name == "weekday"
        assert program.get_weekday_enabled("Monday") is True

        await program.set_weekday_enabled("Monday", False)
        assert program.get_weekday_enabled("Monday") is False

        await program.set_program_schedule_type(3)
        assert program.program_schedule_type_name == "interval_day"
        assert program.interval_days == 1
        assert program.starting_in_days == 0

    @pytest.mark.asyncio
    async def test_set_interval_days(self, controller, program):
        await program.set_program_schedule_type(3)
        await program.set_interval_days(3)
        await program.set_starting_in_days(2)
        assert program.program_schedule_type_name == "interval_day"
        assert program.interval_days == 3
        assert program.starting_in_days == 2

        await program.set_program_schedule_type(0)
        assert program.days1 == 0
        assert program.days0 == 0
