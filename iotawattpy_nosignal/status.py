"""Live readings and device status reported by the IoTaWatt ``/status`` endpoint.

Modified as part of the iotawattpy-nosignal fork
(https://github.com/No-Signal/iotawattpy), see README.md.

The response shapes follow ``handleStatus()`` in the firmware's
``Firmware/IotaWatt/webServer.cpp`` (https://github.com/boblemaire/IoTaWatt).
Fields can be missing on older firmware; they are parsed as ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


def _toFloat(value: Any) -> float | None:
    """Convert a JSON number or numeric string to a finite float, else ``None``."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _toStr(value: Any) -> str | None:
    """Convert a JSON value to str, keeping ``None``."""
    return None if value is None else str(value)


@dataclass(frozen=True)
class LiveReading:
    """A live (about 1 second average) reading of one input or output.

    The firmware's ``statService`` refreshes these values every second. Input
    channels set ``watts`` and ``power_factor`` (power channels) or ``volts``
    and ``hz`` (voltage channels). Outputs set ``value`` and ``unit``, the
    output script evaluated against the same live values.
    """

    watts: float | None = None
    power_factor: float | None = None
    volts: float | None = None
    hz: float | None = None
    value: float | None = None
    unit: str | None = None

    @classmethod
    def fromInput(cls, data: dict[str, Any]) -> LiveReading:
        """Parse an entry of the ``inputs`` array.

        ``Watts`` is sent as a string (``String(value, 0)``) and is zeroed by
        the firmware when its magnitude is below 2 W.
        """
        return cls(
            watts=_toFloat(data.get("Watts")),
            power_factor=_toFloat(data.get("Pf")),
            volts=_toFloat(data.get("Vrms")),
            hz=_toFloat(data.get("Hz")),
        )

    @classmethod
    def fromOutput(cls, data: dict[str, Any]) -> LiveReading:
        """Parse an entry of the ``outputs`` array."""
        return cls(value=_toFloat(data.get("value")), unit=_toStr(data.get("units")))


def parseLiveStatus(data: dict[str, Any]) -> dict[str, LiveReading]:
    """Parse a ``/status?inputs&outputs`` response into live readings.

    Keys match ``Iotawatt.getSensors()`` keys: ``input_{channel}`` and
    ``output_{name}``.
    """
    readings: dict[str, LiveReading] = {}
    for entry in data.get("inputs") or []:
        if entry.get("channel") is not None:
            readings[f"input_{entry['channel']}"] = LiveReading.fromInput(entry)
    for entry in data.get("outputs") or []:
        if entry.get("name") is not None:
            readings[f"output_{entry['name']}"] = LiveReading.fromOutput(entry)
    return readings
