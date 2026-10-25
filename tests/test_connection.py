"""Tests for the HTTP connection helper."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from iotawattpy_nosignal.connection import Connection
from iotawattpy_nosignal.iotawatt import Iotawatt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

HOST = "192.0.2.1"
STATUS_URL = f"http://{HOST}/status"
DIGEST_CHALLENGE = 'Digest realm="iotawatt", nonce="0123456789abcdef", qop="auth"'


@pytest.fixture
async def websession() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


def _mock_digest_device() -> list[int]:
    """Mock a device that requires digest auth.

    Returns the status codes of every response the device sent.
    """
    status_codes: list[int] = []

    def status(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization", "").startswith("Digest "):
            response = httpx.Response(200, json={"wifi": {"mac": "de:ad:be:ef:00:01"}})
        else:
            response = httpx.Response(
                401, headers={"WWW-Authenticate": DIGEST_CHALLENGE}
            )
        status_codes.append(response.status_code)
        return response

    respx.get(STATUS_URL).mock(side_effect=status)
    return status_codes


@respx.mock
async def test_digest_auth_challenge_reused(websession: httpx.AsyncClient) -> None:
    """Only the first request is challenged; later ones reuse the challenge."""
    status_codes = _mock_digest_device()
    connection = Connection(websession, HOST, "user", "pass")

    first = await connection.get(f"{STATUS_URL}?wifi=yes")
    second = await connection.get(f"{STATUS_URL}?inputs=yes")

    assert first.status_code == 200
    assert second.status_code == 200
    assert status_codes == [401, 200, 200]


@respx.mock
async def test_digest_auth_reused_across_iotawatt_requests(
    websession: httpx.AsyncClient,
) -> None:
    """An Iotawatt instance shares one digest auth across its requests."""
    status_codes = _mock_digest_device()
    iotawatt = Iotawatt("test", HOST, websession, "user", "pass")

    assert await iotawatt.connect()
    assert await iotawatt.connect()

    assert status_codes.count(401) == 1


@respx.mock
async def test_no_auth_without_username(websession: httpx.AsyncClient) -> None:
    """Without a username no Authorization header is sent."""
    route = respx.get(STATUS_URL).respond(json={})
    connection = Connection(websession, HOST)

    await connection.get(STATUS_URL)

    assert "Authorization" not in route.calls.last.request.headers
