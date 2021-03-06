import pytest

from pyopensprinkler import Controller as OpenSprinkler
from const import URL, PASSWORD


@pytest.fixture
async def controller():
    controller = OpenSprinkler(URL, PASSWORD)
    yield controller
    await controller.session_close()
