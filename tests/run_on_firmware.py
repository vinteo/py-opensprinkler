import os
import pytest

from pyopensprinkler import Controller as OpenSprinkler

URL = os.environ.get("CONTROLLER_URL") or "http://localhost:8080"
PASSWORD = os.environ.get("CONTROLLER_PASSWORD") or "opendoor"
FIRMWARE_VERSION = float(os.environ.get("CONTROLLER_FIRMWARE") or "219")


@pytest.fixture(scope="function")
async def controller():
    controller = OpenSprinkler(URL, PASSWORD)
    yield controller
    await controller.session_close()


class TestFirmware:
    @pytest.mark.asyncio
    async def test_firmware_version(self, controller):
        await controller.refresh()
        assert controller.firmware_version, int(FIRMWARE_VERSION)
        assert controller.firmware_minor_version >= 0

    @pytest.mark.skipif(FIRMWARE_VERSION > 217, reason="only for version 217 and below")
    @pytest.mark.asyncio
    async def test_last_reboot_time_old(self, controller):
        await controller.refresh()
        assert controller.last_reboot_time == None

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
        assert controller.mac_address == None

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
        assert controller.mqtt_settings == None
        assert controller.mqtt_enabled == None

    @pytest.mark.skipif(
        int(FIRMWARE_VERSION) <= 219, reason="only for version 219 (4) and above"
    )
    @pytest.mark.asyncio
    async def test_mqtt(self, controller):
        await controller.refresh()
        assert controller.mqtt_settings is not None
        assert controller.mqtt_enabled, False

    @pytest.mark.asyncio
    async def test_auto_refresh(self, controller):
        await controller.refresh()
        await controller.stations[0].run()
        assert controller.stations[0].is_running == True

        await controller.stations[0].stop()
        assert controller.stations[0].is_running == False
