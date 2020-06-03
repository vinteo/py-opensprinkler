import os
import pytest

from pyopensprinkler import Controller as OpenSprinkler

URL = os.environ.get("CONTROLLER_URL") or "http://localhost:8080"
PASSWORD = os.environ.get("CONTROLLER_PASSWORD") or "opendoor"
FIRMWARE_VERSION = os.environ.get("CONTROLLER_FIRMWARE") or "219"


class TestFirmware:
    @classmethod
    def setup_class(self):
        self._controller = OpenSprinkler(URL, PASSWORD)

    def test_refresh(self):
        self._controller.refresh()

    @pytest.mark.skipif(FIRMWARE_VERSION != "219", reason="only for version 219")
    def test_skip_example(self):
        return None
