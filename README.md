# Python module for OpenSprinker API

[![PyPI version](https://badge.fury.io/py/pyopensprinkler.svg)](https://badge.fury.io/py/pyopensprinkler)
![PyPI - Downloads](https://img.shields.io/pypi/dm/pyopensprinkler)
![Linting Status](https://github.com/vinteo/py-opensprinkler/workflows/Linting/badge.svg)
[![Build Status](https://travis-ci.org/vinteo/py-opensprinkler.svg?branch=master)](https://travis-ci.org/vinteo/py-opensprinkler)
[![codecov](https://codecov.io/gh/vinteo/py-opensprinkler/branch/master/graph/badge.svg)](https://codecov.io/gh/vinteo/py-opensprinkler)

Tested against OpenSprinkler version 2.1.9.

## Installation

```bash
pip install pyopensprinkler
```

## Usage

```python
from pyopensprinkler import Controller as OpenSprinklerController

controller = OpenSprinklerController("http[s]://hostname[:port]", "password")
await controller.refresh()

version = controller.firmware_version
```

## Commands and Properties

All commands are async.

### Controller

`controller.refresh()`
Refreshes state, programs and stations

`controller.enable()`
Enabled controller operation

`controller.disable()`
Disables controller operation

`controller.programs`

`controller.stations`

### Programs

```python
is_enabled = controller.programs[0].enabled

program = controller.programs[0]
await program.run()
```

`program.enabled`

`program.enable()`

`program.disable()`

`program.run()`

### Stations

```python
is_enabled = controller.stations[0].enabled
status = controller.stations[0].status
station = controller.station[0]
await station.run(120)
```

`station.is_running`

`station.running_program_id`

`station.status`

`station.run(seconds)`
Acceptable range for seconds is 0 to 64800 (18 hours)

`station.stop()`

`station.toggle()`

## Development

OpenSprinkler API documentation available [here](https://openthings.freshdesk.com/support/solutions/articles/5000716363-os-api-documents).

```bash
virtualenv .
source bin/activate

# install requirements
pip install -r requirements.txt

# install dev requirements
pip install -r requirements-dev.txt

# one-time install commit hooks
pre-commit install

deactivate
```
