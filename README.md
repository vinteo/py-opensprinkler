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
version = os.device.firmware_version()
```

## Commands

`os.programs`

`os.stations`

### Device

`os.device.firmware_version`

`os.device.hardware_version`

`os.device.last run`

`os.device.get_rain_delay`

`os.device.rain_delay_stop_time`

`os.device.rain_sensor_1`

`os.device.rain_sensor_2`

`os.device.rain_sensor_legacy`
Rain sensor for firmware version <= 2.1.7

`os.device.operation_enabled`

`os.device.water_level`

`os.device.enable()`

`os.device.disable()`

### Programs

```python
is_enabled = os.programs[0].enabled

program = os.programs[0]
program.run()
```

`program.enabled`

`program.enable()`

`program.disable()`

`program.run()`

### Stations

```python
isEnabled = os.stations[0].status
station = os.station[0]
station.run(120)
```

`station.is_running`

`station.running_program_id`

`station.status`

`station.run(seconds)`
 Acceptable range for seconds is 0 to 64800 (18 hours)

`station.stop()`
