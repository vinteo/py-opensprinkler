import asyncio

import pytest
from const import FIRMWARE_VERSION


class TestController:
    @pytest.mark.asyncio
    async def test_firmware_version(self, controller):
        await controller.refresh()
        assert controller.firmware_version, int(FIRMWARE_VERSION)
        assert controller.firmware_minor_version >= 0

    @pytest.mark.skipif(FIRMWARE_VERSION > 217, reason="only for version 217 and below")
    @pytest.mark.asyncio
    async def test_last_reboot_time_old(self, controller):
        await controller.refresh()
        assert controller.last_reboot_time is None

    @pytest.mark.skipif(
        FIRMWARE_VERSION <= 217, reason="only for version 218 and above"
    )
    @pytest.mark.asyncio
    async def test_last_reboot_time_new(self, controller):
        await controller.refresh()
        assert controller.last_reboot_time >= 0

    @pytest.mark.skipif(FIRMWARE_VERSION > 219, reason="only for version 219 and below")
    @pytest.mark.asyncio
    async def test_no_mac_address(self, controller):
        await controller.refresh()
        assert controller.mac_address is None

    @pytest.mark.skipif(
        int(FIRMWARE_VERSION) <= 219, reason="only for version 219 (4) and above"
    )
    @pytest.mark.asyncio
    async def test_mac_address(self, controller):
        await controller.refresh()
        assert len(controller.mac_address), 17

    @pytest.mark.skipif(FIRMWARE_VERSION > 219, reason="only for version 219 and below")
    @pytest.mark.asyncio
    async def test_no_mqtt(self, controller):
        await controller.refresh()
        assert controller.mqtt_settings is None
        assert controller.mqtt_enabled is None

    @pytest.mark.skipif(
        int(FIRMWARE_VERSION) < 220, reason="only for version 220 (1) and above"
    )
    @pytest.mark.asyncio
    async def test_mqtt(self, controller):
        await controller.refresh()
        assert controller.mqtt_settings is not None

    @pytest.mark.asyncio
    async def test_auto_refresh(self, controller):
        await controller.refresh()
        await controller.stations[0].run()
        await asyncio.sleep(1)
        assert controller.stations[0].is_running

        await controller.stations[0].stop()
        await asyncio.sleep(1)
        assert not controller.stations[0].is_running

    @pytest.mark.asyncio
    async def test_create_delete_program(self, controller):
        await controller.refresh()
        assert len(controller.programs) == 0

        await controller.create_program("test program")
        assert len(controller.programs) == 1

        await controller.delete_program(0)
        assert len(controller.programs) == 0

    @pytest.mark.asyncio
    async def test_rain_delay(self, controller):
        await controller.refresh()

        # Disable rain delay
        await controller.disable_rain_delay()
        assert not controller.rain_delay_active
        assert controller.rain_delay_stop_time == 0

        # Enable rain delay and verify state and stop time
        DELAY_HOURS = 2
        await controller.set_rain_delay(DELAY_HOURS)
        assert controller.rain_delay_active
        # Check timezone-corrected stop time within 30-second margin of
        # error for slow test execution
        assert (
            abs(
                controller.rain_delay_stop_time
                - (controller.device_time + DELAY_HOURS * 60 * 60)
            )
            < 30
        )

        # Setting 0 hour delay clears the rain delay
        await controller.set_rain_delay(0)
        assert not controller.rain_delay_active
        assert controller.rain_delay_stop_time == 0

        # Valid range which can be converted for OpenSprinkler is 0 to 32767.
        with pytest.raises(ValueError):
            await controller.set_rain_delay(-1)
        with pytest.raises(ValueError):
            await controller.set_rain_delay(32768)

    @pytest.mark.skipif(FIRMWARE_VERSION < 220, reason="only for version 220 and above")
    @pytest.mark.asyncio
    async def test_pause(self, controller):
        await controller.refresh()

        # Disable pause
        await controller.disable_pause()
        assert not controller.pause_active
        assert controller.pause_time_remaining == 0

        # Enable pause and verify the state and pause time
        PAUSE_SECONDS = 600
        await controller.set_pause(PAUSE_SECONDS)
        await controller.refresh()

        assert controller.pause_active
        assert controller.pause_time_remaining > PAUSE_SECONDS - 30
        assert controller.pause_time_remaining <= PAUSE_SECONDS

        # Now try to alter the pause time. This relies on the controller detecting that it is
        # currently in a pause, clearing it, and setting the new pause duration.
        PAUSE_SECONDS = 200
        await controller.set_pause(PAUSE_SECONDS)
        await controller.refresh()

        assert controller.pause_active
        assert controller.pause_time_remaining > PAUSE_SECONDS - 30
        assert controller.pause_time_remaining <= PAUSE_SECONDS

        # Setting 0 second pause clears the pause
        await controller.set_pause(0)
        assert not controller.pause_active
        assert controller.pause_time_remaining == 0

        # Valid range of 0-86400 chosen since the UI cannot display greater values.
        with pytest.raises(ValueError):
            await controller.set_pause(-1)
        with pytest.raises(ValueError):
            await controller.set_pause(86400 + 1)
