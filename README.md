![CI](https://github.com/No-Signal/iotawattpy/actions/workflows/ci.yml/badge.svg)

> **Fork notice:** this is a modified fork of
> [home-assistant-libs/iotawattpy](https://github.com/home-assistant-libs/iotawattpy),
> forked at commit `42d4d6e` (the commit after `v0.3.0`). It is renamed to
> `iotawattpy-nosignal` (import package `iotawattpy_nosignal`) so it cannot clash
> with the upstream `ha-iotawattpy` package. It is **not** published to PyPI; it
> is bundled into the [No-Signal/ha-iotawatt](https://github.com/No-Signal/ha-iotawatt)
> Home Assistant custom integration. The changes are listed in
> [CHANGELOG.md](CHANGELOG.md). Licensed under GPL-3.0-or-later, like upstream.

# iotawattpy-nosignal
 Python interface for the IoTaWatt device

## Usage

```python
import httpx
from iotawattpy_nosignal.iotawatt import Iotawatt

async with httpx.AsyncClient() as session:
    iotawatt = Iotawatt("iotawatt", "192.0.2.1", session)
    await iotawatt.connect()
    print(iotawatt.getMacAddress())

    await iotawatt.update(timespan=30)  # averages over the last 30 s
    sensors = iotawatt.getSensors()["sensors"]

    live = await iotawatt.getLiveStatus()
    print(live["input_1"].watts, sensors["input_1"].getName())

    status = await iotawatt.getDeviceStatus()
    print(status.stats.version if status.stats else None)
```

### `update(timespan=30, lastUpdate=None)`

Reads sensors through the device's `/query` API, which works on the 5 second
datalog. `timespan` is the averaging window for current values, so pass your
poll interval (a multiple of 5 s). Each update makes four requests (plus one
the first time lifetime sensors are used). Calling it twice within one 5 s
slot refreshes the current values and skips the interval energy query; this
is logged at debug level.

### `getMacAddress() -> str`

The MAC address captured by `connect()`, without colons. Empty until
`connect()` has succeeded.

### `getLiveStatus() -> dict[str, LiveReading]`

Live readings from one `/status?inputs=yes&outputs=yes` request, keyed like
`getSensors()` (`input_{channel}`, `output_{name}`). It does not need
`update()` to have run.

These are the values the device's own Status page shows. The firmware's
`statService` runs every second and keeps roughly one second averages
(damped only while a value stays within 2% of the previous one, so step
changes show up in the next value). Polling this endpoint every second
gives near-real-time power, while `update()` is limited to the 5 s datalog.

`LiveReading` is a frozen dataclass: inputs set `watts` and `power_factor`
(power channels) or `volts` and `hz` (voltage channels); outputs set `value`
and `unit`. Anything the firmware does not send is `None`. The firmware
reports power below 2 W as 0.

### `getDeviceStatus() -> DeviceStatus`

Device health from one
`/status?device=yes&stats=yes&wifi=yes&datalogs=yes&uploaders=yes` request,
as frozen dataclasses: `device` (`DeviceSettings`), `stats` (`DeviceStats`:
sample rates, start time, free heap, firmware version, RTC battery),
`wifi` (`WifiStatus`), `datalogs` (`DatalogStatus`, also via
`getDatalog("Current")`) and `uploaders` (`UploaderStatus`). UNIX times are
aware UTC datetimes (0 becomes `None`). Sections and fields missing on older
firmware are `None`. The firmware version is kept as reported (e.g.
`02_08_04`).

### Request serialisation and authentication

The firmware's web server (`ESP8266WebServer`) handles one connection at a
time. Each `Iotawatt` instance therefore sends its requests one after the
other, so share one instance per device between pollers (for example a
30 s `update()` loop and a 1 s `getLiveStatus()` loop) rather than creating
several.

With a username, one digest-auth object is reused for all requests, so only
the first request pays for the authentication challenge.

## Bundling

The package is copied verbatim into the integration, so it must keep two
properties, both enforced by `tests/test_bundling.py`:

- every import of the package's own modules is relative
  (`from .connection import Connection`), never absolute;
- its only runtime dependency is `httpx`.

## Releasing

Releases are not published to PyPI. To release:

1. Bump the version on `main`: `uv version <new-version>` (updates
   `pyproject.toml` and `uv.lock`), add a `CHANGELOG.md` entry, then commit.
2. Create an annotated `v<new-version>` tag (e.g. `v0.4.0`), push it and
   create a GitHub release from it.
3. The release workflow builds the package and checks that it installs and
   imports. It fails if the tag does not match the project version.
