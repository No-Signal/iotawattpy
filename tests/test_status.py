"""Tests for live readings and device status from the /status endpoint.

Fixtures follow the shapes produced by handleStatus() in the firmware's
Firmware/IotaWatt/webServer.cpp (https://github.com/boblemaire/IoTaWatt).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx

from iotawattpy_nosignal.iotawatt import Iotawatt
from iotawattpy_nosignal.status import LiveReading, parseLiveStatus

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
