import os
import pytest

from pyopensprinkler import Controller as OpenSprinkler

URL = os.environ.get("CONTROLLER_URL") or "http://localhost:8080"
PASSWORD = os.environ.get("CONTROLLER_PASSWORD") or "opendoor"
FIRMWARE_VERSION = float(os.environ.get("CONTROLLER_FIRMWARE") or "219")


class TestFirmware:
    @classmethod
    def setup_class(self):
        self._controller = OpenSprinkler(URL, PASSWORD)

    async def test_firmware_version(self):
        await self._controller.refresh()
        assert self._controller.firmware_version, int(FIRMWARE_VERSION)
        assert self._controller.firmware_minor_version >= 0

    @pytest.mark.skipif(FIRMWARE_VERSION > 217, reason="only for version 217 and below")
    async def test_last_reboot_time_old(self):
        await self._controller.refresh()
        assert self._controller.last_reboot_time == None

    @pytest.mark.skipif(
        FIRMWARE_VERSION <= 217, reason="only for version 218 and above"
    )
    async def test_last_reboot_time_new(self):
        await self._controller.refresh()
        assert self._controller.last_reboot_time >= 0

    @pytest.mark.skipif(FIRMWARE_VERSION > 219, reason="only for version 219 and below")
    async def test_no_mac_address(self):
        await self._controller.refresh()
        assert self._controller.mac_address == None

    @pytest.mark.skipif(
        int(FIRMWARE_VERSION) <= 219, reason="only for version 219 (4) and above"
    )
    async def test_mac_address(self):
        await self._controller.refresh()
        assert len(self._controller.mac_address), 17

    @pytest.mark.skipif(FIRMWARE_VERSION > 219, reason="only for version 219 and below")
    async def test_no_mqtt(self):
        await self._controller.refresh()
        assert self._controller.mqtt_settings == None
        assert self._controller.mqtt_enabled == None

    @pytest.mark.skipif(
        int(FIRMWARE_VERSION) <= 219, reason="only for version 219 (4) and above"
    )
    async def test_mqtt(self):
        await self._controller.refresh()
        assert self._controller.mqtt_settings is not None
        assert self._controller.mqtt_enabled, False
