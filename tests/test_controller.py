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
        int(FIRMWARE_VERSION) <= 219, reason="only for version 219 (4) and above"
    )
    @pytest.mark.asyncio
    async def test_mqtt(self, controller):
        await controller.refresh()
        assert controller.mqtt_settings is not None
        assert not controller.mqtt_enabled

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
