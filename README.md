# py-opensprinkler

Python module for OpenSprinker API. Tested against OpenSprinkler version 2.1.9.

## Installation

```
pip install pyopensprinkler
```

## Usage

```python
from pyopensprinkler import OpenSprinkler

os = OpenSprinkler("hostname:port", "md5password")
version = os.device.getFirmwareVersion()
```

## Commands

`os.getPrograms()`

`os.getProgram(index)`
Index starts from 0

`os.getStations()`

`os.getStation(index)`
Index starts from 0

### Device

`os.device.getFirmwareVersion()`

`os.device.getHardwareVersion()`

`os.device.getLastRun()`

`os.device.getRainDelay()`

`os.device.getRainDelayStopTime()`

`os.device.getRainSensor1()`

`os.device.getRainSensor2()`

`os.device.getRainSensorLegacy()`
Rain sensor for firmware version <= 2.1.7

`os.device.getOperationEnabled()`

`os.device.getWaterLevel()`

`os.device.enable()`

`os.device.disable()`

### Programs

```python
programs = os.getPrograms()
isEnabled = program[0].getEnabled()

program = os.getProgram(0)
program.run()
```

`program.getEnabled()`

`program.enable()`

`program.disable()`

`program.run()`

### Stations

```python
stations = os.getStations()
isEnabled = stations[0].getStatus()

station = os.getStation(0)
station.run(120)
```

`station.getIsRunning()`

`station.getRunningProgramId()`

`station.getStatus()`

`station.run(seconds)`
 Acceptable range for seconds is 0 to 64800 (18 hours)

`station.stop()`
