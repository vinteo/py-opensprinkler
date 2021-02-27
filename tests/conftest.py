import pytest
from const import PASSWORD, URL
from pyopensprinkler import Controller as OpenSprinkler


@pytest.fixture
async def controller():
    controller = OpenSprinkler(URL, PASSWORD)
    yield controller
    await controller.session_close()
