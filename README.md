# py-opensprinkler

Python module for OpenSprinker API. Tested against OpenSprinkler version 2.1.9.

## Usage

```python
from pyopensprinkler import OpenSprinkler

os = OpenSprinkler("hostname:port", "md5password")
os.device.getFirmwareVersion()
```

## Commands

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

`os.device.enable()`

`os.device.disable()`
