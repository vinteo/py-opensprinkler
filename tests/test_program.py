import pytest


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
