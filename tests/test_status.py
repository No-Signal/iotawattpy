"""Tests for live readings and device status from the /status endpoint.

Fixtures follow the shapes produced by handleStatus() in the firmware's
Firmware/IotaWatt/webServer.cpp (https://github.com/boblemaire/IoTaWatt).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx

from iotawattpy_nosignal.iotawatt import Iotawatt
from iotawattpy_nosignal.status import (
    DatalogStatus,
    DeviceSettings,
    DeviceStats,
    DeviceStatus,
    LiveReading,
    UploaderStatus,
    WifiStatus,
    parseLiveStatus,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

HOST = "192.0.2.1"

# Current firmware (02_08_xx): voltage channel, power channels (one reversed,
# one below the 2 W cut-off) and two outputs.
STATUS_LIVE: dict[str, Any] = {
    "inputs": [
        {"channel": 0, "Vrms": 121.437, "Hz": 59.982, "phase": 0},
        {"channel": 1, "Watts": "1523", "Pf": 0.981, "phase": 1.42, "lastphase": 1.4},
        {
            "channel": 2,
            "Watts": "-842",
            "Pf": 0.873,
            "reversed": True,
            "phase": 2.1,
            "lastphase": 2.1,
        },
        {"channel": 3, "Watts": "0", "Pf": 0, "phase": 0, "lastphase": 0},
    ],
    "outputs": [
        {"name": "Total_power", "units": "Watts", "value": 2365.2},
        {"name": "Mains_volts", "units": "Volts", "value": 121.437},
    ],
}

# Older firmware: no power factor, phase or frequency.
STATUS_LIVE_OLD: dict[str, Any] = {
    "inputs": [
        {"channel": 0, "Vrms": 230.1},
        {"channel": 1, "Watts": "87"},
    ],
    "outputs": [{"name": "Total", "units": "Watts", "value": 87}],
}

# Current firmware, all sections requested by getDeviceStatus().
STATUS_DEVICE: dict[str, Any] = {
    "device": {
        "name": "IotaWatt",
        "timediff": -300,
        "allowdst": True,
        "update": "MAJOR",
    },
    "stats": {
        "cyclerate": 412.5,
        "chanrate": 38.9,
        "starttime": 1761300000,
        "currenttime": 1761400000,
        "runseconds": 100000,
        "stack": 18640,
        "version": "02_08_04",
        "frequency": 59.98,
        "lowbat": False,
    },
    "wifi": {
        "connecttime": 1761300042,
        "SSID": "home",
        "IP": "192.0.2.1",
        "channel": 6,
        "RSSI": -61,
        "mac": "A0:20:A6:00:00:01",
    },
    "datalogs": [
        {
            "id": "Current",
            "firstkey": 1700000000,
            "lastkey": 1761399995,
            "size": 61440000,
            "interval": 5,
        },
        {
            "id": "History",
            "firstkey": 1600000000,
            "lastkey": 1761399960,
            "size": 3840000,
            "interval": 60,
        },
        {"id": "Solar", "firstkey": 0, "lastkey": 0, "size": 0, "interval": 5},
    ],
    "uploaders": [
        {"id": "influxDB", "status": "running", "lastpost": 1761399990},
        {
            "id": "PVoutput",
            "status": "stopped",
            "lastpost": 0,
            "message": "Invalid API key",
        },
    ],
}

# Older firmware: no device section, no uploaders or lowbat, WiFi
# disconnected (only connecttime is sent).
STATUS_DEVICE_OLD: dict[str, Any] = {
    "stats": {
        "cyclerate": 400,
        "chanrate": 30,
        "starttime": 1600000000,
        "currenttime": 1600001000,
        "runseconds": 1000,
        "stack": 20000,
        "version": "02_03_20",
        "frequency": 50,
    },
    "wifi": {"connecttime": 0},
    "datalogs": [{"id": "Current", "firstkey": 1500000000, "lastkey": 1600000995}],
}


def _utc(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


@pytest.fixture
async def websession() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


def test_parse_live_status() -> None:
    """Inputs and outputs are keyed like getSensors() and fully parsed."""
    readings = parseLiveStatus(STATUS_LIVE)

    assert set(readings) == {
        "input_0",
        "input_1",
        "input_2",
        "input_3",
        "output_Total_power",
        "output_Mains_volts",
    }
    assert readings["input_0"] == LiveReading(volts=121.437, hz=59.982)
    assert readings["input_1"] == LiveReading(watts=1523.0, power_factor=0.981)
    assert readings["input_2"].watts == -842.0
    assert readings["input_3"].watts == 0.0
    assert readings["output_Total_power"] == LiveReading(value=2365.2, unit="Watts")
    assert readings["output_Mains_volts"] == LiveReading(value=121.437, unit="Volts")


def test_parse_live_status_watts_is_a_string() -> None:
    """Watts arrives as a JSON string and is converted to float."""
    reading = parseLiveStatus(STATUS_LIVE)["input_1"]

    assert isinstance(reading.watts, float)


def test_parse_live_status_old_firmware() -> None:
    """Missing keys become None instead of raising."""
    readings = parseLiveStatus(STATUS_LIVE_OLD)

    assert readings["input_0"] == LiveReading(volts=230.1)
    assert readings["input_1"] == LiveReading(watts=87.0)
    assert readings["output_Total"] == LiveReading(value=87.0, unit="Watts")


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="empty"),
        pytest.param({"inputs": None, "outputs": None}, id="null-arrays"),
        pytest.param({"inputs": [{"Watts": "5"}], "outputs": [{}]}, id="no-ids"),
    ],
)
def test_parse_live_status_incomplete(data: dict[str, Any]) -> None:
    """Responses without usable entries give no readings."""
    assert parseLiveStatus(data) == {}


def test_parse_live_status_unparsable_values() -> None:
    """Values that are not numbers become None."""
    readings = parseLiveStatus(
        {
            "inputs": [
                {"channel": 1, "Watts": "nan?", "Pf": True},
                {"channel": 2, "Watts": "inf", "Pf": float("nan")},
            ],
            "outputs": [{"name": "x", "units": "Watts", "value": "n/a"}],
        }
    )

    assert readings["input_1"] == LiveReading()
    assert readings["input_2"] == LiveReading()
    assert readings["output_x"] == LiveReading(unit="Watts")


def test_live_reading_is_frozen() -> None:
    reading = LiveReading(watts=1.0)

    with pytest.raises(AttributeError):
        reading.watts = 2.0  # type: ignore[misc]


@respx.mock
async def test_get_live_status(websession: httpx.AsyncClient) -> None:
    """One request, without connect() or update() having run."""
    route = respx.get(
        f"http://{HOST}/status", params={"inputs": "yes", "outputs": "yes"}
    ).respond(json=STATUS_LIVE)
    iotawatt = Iotawatt("test", HOST, websession)

    readings = await iotawatt.getLiveStatus()

    assert route.call_count == 1
    assert len(respx.calls) == 1
    assert readings["input_1"].watts == 1523.0
    assert readings["output_Total_power"].value == 2365.2


@respx.mock
async def test_get_live_status_http_error(websession: httpx.AsyncClient) -> None:
    """HTTP errors propagate to the caller."""
    respx.get(f"http://{HOST}/status").respond(status_code=500)
    iotawatt = Iotawatt("test", HOST, websession)

    with pytest.raises(httpx.HTTPStatusError):
        await iotawatt.getLiveStatus()


def test_parse_device_status() -> None:
    """Every section and field of a current firmware response is parsed."""
    status = DeviceStatus.fromJson(STATUS_DEVICE)

    assert status.device == DeviceSettings(
        name="IotaWatt", timediff=-300, allowdst=True, update="MAJOR"
    )
    assert status.stats == DeviceStats(
        cyclerate=412.5,
        chanrate=38.9,
        starttime=_utc(1761300000),
        currenttime=_utc(1761400000),
        runseconds=100000,
        stack=18640,
        version="02_08_04",
        frequency=59.98,
        lowbat=False,
    )
    assert status.wifi == WifiStatus(
        connecttime=_utc(1761300042),
        ssid="home",
        ip="192.0.2.1",
        channel=6,
        rssi=-61,
        mac="A0:20:A6:00:00:01",
    )
    assert status.datalogs == (
        DatalogStatus(
            id="Current",
            firstkey=_utc(1700000000),
            lastkey=_utc(1761399995),
            size=61440000,
            interval=5,
        ),
        DatalogStatus(
            id="History",
            firstkey=_utc(1600000000),
            lastkey=_utc(1761399960),
            size=3840000,
            interval=60,
        ),
        DatalogStatus(id="Solar", firstkey=None, lastkey=None, size=0, interval=5),
    )
    assert status.uploaders == (
        UploaderStatus(
            id="influxDB", status="running", lastpost=_utc(1761399990), message=None
        ),
        UploaderStatus(
            id="PVoutput", status="stopped", lastpost=None, message="Invalid API key"
        ),
    )


def test_device_status_times_are_aware_utc() -> None:
    status = DeviceStatus.fromJson(STATUS_DEVICE)

    assert status.stats is not None
    assert status.stats.starttime is not None
    assert status.stats.starttime.tzinfo is UTC
    assert status.stats.starttime == datetime(2025, 10, 24, 10, 0, tzinfo=UTC)


def test_device_status_version_not_reformatted() -> None:
    status = DeviceStatus.fromJson(STATUS_DEVICE)

    assert status.stats is not None
    assert status.stats.version == "02_08_04"


def test_parse_device_status_old_firmware() -> None:
    """Missing sections and fields become None instead of raising."""
    status = DeviceStatus.fromJson(STATUS_DEVICE_OLD)

    assert status.device is None
    assert status.uploaders is None
    assert status.stats is not None
    assert status.stats.lowbat is None
    assert status.stats.cyclerate == 400.0
    assert status.wifi == WifiStatus(
        connecttime=None, ssid=None, ip=None, channel=None, rssi=None, mac=None
    )
    assert status.datalogs == (
        DatalogStatus(
            id="Current",
            firstkey=_utc(1500000000),
            lastkey=_utc(1600000995),
            size=None,
            interval=None,
        ),
    )


def test_parse_device_status_empty() -> None:
    assert DeviceStatus.fromJson({}) == DeviceStatus(
        device=None, stats=None, wifi=None, datalogs=None, uploaders=None
    )


def test_parse_device_status_skips_entries_without_id() -> None:
    status = DeviceStatus.fromJson(
        {"datalogs": [{"firstkey": 1}, "junk"], "uploaders": [{"status": "running"}]}
    )

    assert status.datalogs == ()
    assert status.uploaders == ()


def test_get_datalog() -> None:
    status = DeviceStatus.fromJson(STATUS_DEVICE)

    current = status.getDatalog("Current")
    assert current is not None
    assert current.lastkey == _utc(1761399995)
    assert status.getDatalog("Missing") is None
    assert DeviceStatus.fromJson({}).getDatalog("Current") is None


@respx.mock
async def test_get_device_status(websession: httpx.AsyncClient) -> None:
    """One request for all sections, without connect() or update()."""
    route = respx.get(
        f"http://{HOST}/status",
        params={
            "device": "yes",
            "stats": "yes",
            "wifi": "yes",
            "datalogs": "yes",
            "uploaders": "yes",
        },
    ).respond(json=STATUS_DEVICE)
    iotawatt = Iotawatt("test", HOST, websession)

    status = await iotawatt.getDeviceStatus()

    assert route.call_count == 1
    assert len(respx.calls) == 1
    assert status == DeviceStatus.fromJson(STATUS_DEVICE)


@respx.mock
async def test_get_device_status_http_error(websession: httpx.AsyncClient) -> None:
    respx.get(f"http://{HOST}/status").respond(status_code=401)
    iotawatt = Iotawatt("test", HOST, websession)

    with pytest.raises(httpx.HTTPStatusError):
        await iotawatt.getDeviceStatus()
