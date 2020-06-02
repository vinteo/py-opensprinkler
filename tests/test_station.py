from pyopensprinkler.station import Station
from tests.mocks.controller import MockController


class TestStation:
    def test_index(self):
        station = Station({}, 1)
        assert station.index == 1

    def test_name(self):
        mockController = MockController({"stations": {"snames": {1: "Station Name"}}})
        station = Station(mockController, 1)
        assert station.name == "Station Name"

    def test_is_running(self):
        mockController = MockController({"status": {"sn": [0, 1]}})
        station = Station(mockController, 1)
        assert station.is_running == True
