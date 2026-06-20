"""Tests for gw2_client retry and error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gw2_progression.gw2_client import Gw2ApiError, _close_client, _get, _get_client


@pytest.fixture(autouse=True)
async def reset_client():
    await _close_client()
    yield
    await _close_client()


def _mock_response(status_code, json_data=None, text=""):
    m = MagicMock(spec=httpx.Response)
    m.status_code = status_code
    m.is_success = 200 <= status_code < 300
    m.json.return_value = json_data or {}
    m.text = text
    return m


@patch("gw2_progression.gw2_client._get_client")
@pytest.mark.asyncio
async def test_get_success(mock_client_factory):
    mock_client = AsyncMock()
    mock_client.get.return_value = _mock_response(200, {"id": 1})
    mock_client_factory.return_value = mock_client
    result = await _get("/v2/test", "key")
    assert result == {"id": 1}


@patch("gw2_progression.gw2_client._get_client")
@pytest.mark.asyncio
async def test_get_401_raises_immediately(mock_client_factory):
    mock_client = AsyncMock()
    mock_client.get.return_value = _mock_response(401)
    mock_client_factory.return_value = mock_client
    with pytest.raises(Gw2ApiError) as exc:
        await _get("/v2/test", "key")
    assert exc.value.status_code == 401


@patch("gw2_progression.gw2_client._get_client")
@pytest.mark.asyncio
async def test_get_500_retries_then_raises(mock_client_factory):
    mock_client = AsyncMock()
    mock_client.get.return_value = _mock_response(500, text="Server Error")
    mock_client_factory.return_value = mock_client
    with pytest.raises(Gw2ApiError) as exc:
        await _get("/v2/test", "key")
    assert exc.value.status_code == 500
    assert mock_client.get.call_count == 3


@patch("gw2_progression.gw2_client._get_client")
@pytest.mark.asyncio
async def test_get_500_then_200_succeeds(mock_client_factory):
    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        _mock_response(500, text="Server Error"),
        _mock_response(500, text="Server Error"),
        _mock_response(200, {"ok": True}),
    ]
    mock_client_factory.return_value = mock_client
    result = await _get("/v2/test", "key")
    assert result == {"ok": True}
    assert mock_client.get.call_count == 3


@patch("gw2_progression.gw2_client._get_client")
@pytest.mark.asyncio
async def test_get_timeout_retries(mock_client_factory):
    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        httpx.TimeoutException("timeout"),
        httpx.ConnectError("refused"),
        _mock_response(200, {"ok": True}),
    ]
    mock_client_factory.return_value = mock_client
    result = await _get("/v2/test", "key")
    assert result == {"ok": True}
    assert mock_client.get.call_count == 3


@patch("gw2_progression.gw2_client._get_client")
@pytest.mark.asyncio
async def test_get_404_not_retried(mock_client_factory):
    mock_client = AsyncMock()
    mock_client.get.return_value = _mock_response(404, text="Not Found")
    mock_client_factory.return_value = mock_client
    with pytest.raises(Gw2ApiError) as exc:
        await _get("/v2/test", "key")
    assert exc.value.status_code == 404
    assert mock_client.get.call_count == 1


@patch("gw2_progression.gw2_client._get_client")
@pytest.mark.asyncio
async def test_client_reuse(mock_client_factory):
    client_instance = AsyncMock()
    mock_client_factory.return_value = client_instance

    c1 = await _get_client()
    c2 = await _get_client()
    assert c1 is c2
