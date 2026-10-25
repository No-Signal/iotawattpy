# Changelog

This is the changelog of `iotawattpy-nosignal`, a fork of
[home-assistant-libs/iotawattpy](https://github.com/home-assistant-libs/iotawattpy).
Versions before 0.4.0 are upstream `ha-iotawattpy` releases.

## 0.4.0

Forked from upstream at `42d4d6e` (the commit after `v0.3.0`).

Firmware references below are to
[boblemaire/IoTaWatt](https://github.com/boblemaire/IoTaWatt):
`handleStatus()` in `Firmware/IotaWatt/webServer.cpp`, `statService.cpp`
(`statServiceInterval = 1`) and the Status page in `SD/index.htm`
(`statusGet`/`statusDisplay`, polling every 1000 ms).

### Changed

- Renamed the distribution to `iotawattpy-nosignal` and the import package
  to `iotawattpy_nosignal`, so it cannot clash with `ha-iotawattpy`. It is
  not published to PyPI; it is bundled into
  [No-Signal/ha-iotawatt](https://github.com/No-Signal/ha-iotawatt). The
  release workflow no longer publishes to PyPI.
- One `httpx.DigestAuth` is created per device and reused for every
  request, so its cached challenge saves the 401 round trip that every
  request used to cost with a password. `Connection` now takes the
  credentials; `Connection.get()` no longer accepts them.
- Requests to one device are serialised with an `asyncio.Lock` in
  `Connection`, because the firmware's `ESP8266WebServer` serves one
  connection at a time.
- "Nothing to query, update() called too soon" is logged at debug instead
  of warning level. Two updates in the same 5 s slot are normal when
  polling at the 5 s datalog resolution; current values are still
  refreshed.

### Added

- `Iotawatt.getMacAddress()`: the MAC address captured by `connect()`.
- `Iotawatt.getLiveStatus()` and `LiveReading`: live readings of every
  active input and output from one `/status?inputs=yes&outputs=yes`
  request, keyed like `getSensors()`. These are the firmware's ~1 s
  `statRecord` averages, the data the device's Status page shows every
  second. `Watts` is parsed from its string form (`String(value, 0)`).
- `Iotawatt.getDeviceStatus()` and `DeviceStatus` (with `DeviceSettings`,
  `DeviceStats`, `WifiStatus`, `DatalogStatus` and `UploaderStatus`):
  device, stats, WiFi, datalog and uploader status from one
  `/status?device=yes&stats=yes&wifi=yes&datalogs=yes&uploaders=yes`
  request. UNIX times are aware UTC datetimes (0 is `None`); fields missing
  on older firmware are `None`.
- Tests that fail on absolute self-imports or runtime dependencies other
  than `httpx`, which bundling relies on.
