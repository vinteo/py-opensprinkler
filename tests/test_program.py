import pytest


@pytest.fixture
async def program(controller):
    await controller.create_program("test program")
    program = controller.programs[0]
    yield program
    await controller.delete_program(0)


class TestProgram:
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
