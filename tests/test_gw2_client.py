"""Tests for gw2_client retry and error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gw2_progression.gw2_client import (
    Gw2ApiError,
    _close_client,
    _get,
    _get_client,
    fetch_account,
    fetch_builds,
    fetch_characters,
    fetch_guilds,
    fetch_tokeninfo,
    fetch_wallet,
    fetch_wvw_stats,
)


@pytest.fixture(autouse=True)
async def reset_client():
    await _close_client()
    yield
    await _close_client()


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("gw2_progression.gw2_client.asyncio.sleep"):
        yield


def _mock_response(status_code, json_data=None, text=""):
    m = MagicMock(spec=httpx.Response)
    m.status_code = status_code
    m.is_success = 200 <= status_code < 300
    m.json.return_value = json_data or {}
    m.text = text
    return m


# ── _get core tests ──


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
    assert mock_client.get.call_count == 1


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
async def test_get_all_timeouts_raises(mock_client_factory):
    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        httpx.TimeoutException("timeout 1"),
        httpx.TimeoutException("timeout 2"),
        httpx.TimeoutException("timeout 3"),
    ]
    mock_client_factory.return_value = mock_client
    with pytest.raises(Gw2ApiError) as exc:
        await _get("/v2/test", "key")
    assert exc.value.status_code == 0
    assert "timeout" in exc.value.message
    assert mock_client.get.call_count == 3


@patch("gw2_progression.gw2_client._get_client")
@pytest.mark.asyncio
async def test_client_reuse(mock_client_factory):
    client_instance = AsyncMock()
    mock_client_factory.return_value = client_instance
    c1 = await _get_client()
    c2 = await _get_client()
    assert c1 is c2


@pytest.mark.asyncio
async def test_client_close():
    await _close_client()
    c = await _get_client()
    assert c is not None
    await _close_client()


# ── fetch_* delegation tests ──


@patch("gw2_progression.gw2_client._get")
@pytest.mark.asyncio
async def test_fetch_tokeninfo(mock_get):
    mock_get.return_value = {"id": "test"}
    result = await fetch_tokeninfo("key")
    assert result == {"id": "test"}
    mock_get.assert_called_with("/v2/tokeninfo", "key")


@patch("gw2_progression.gw2_client._get")
@pytest.mark.asyncio
async def test_fetch_account(mock_get):
    mock_get.return_value = {"name": "Test"}
    result = await fetch_account("key")
    assert result == {"name": "Test"}
    mock_get.assert_called_with("/v2/account", "key")


@patch("gw2_progression.gw2_client._get")
@pytest.mark.asyncio
async def test_fetch_characters(mock_get):
    mock_get.return_value = []
    result = await fetch_characters("key")
    assert result == []
    mock_get.assert_called_with("/v2/characters?ids=all", "key")


@patch("gw2_progression.gw2_client._get")
@pytest.mark.asyncio
async def test_fetch_wallet(mock_get):
    mock_get.return_value = []
    data = await fetch_wallet("key")
    assert data == []


@patch("gw2_progression.gw2_client._get")
@pytest.mark.asyncio
async def test_fetch_guilds_empty(mock_get):
    result = await fetch_guilds("key", None)
    assert result == []
    mock_get.assert_not_called()


@patch("gw2_progression.gw2_client._get")
@pytest.mark.asyncio
async def test_fetch_guilds_with_ids(mock_get):
    mock_get.return_value = [{"id": "g1"}]
    result = await fetch_guilds("key", ["g1", "g2"])
    assert result == [{"id": "g1"}]
    mock_get.assert_called_with("/v2/guild?ids=g1,g2", "key")


@pytest.mark.asyncio
async def test_fetch_wvw_stats():
    result = await fetch_wvw_stats("team1", 5)
    assert result == {"wvw_team": "team1", "account_wvw_rank": 5}


@patch("gw2_progression.gw2_client._get")
@pytest.mark.asyncio
async def test_fetch_builds(mock_get):
    mock_get.return_value = {"equipment_tabs": []}
    data = await fetch_builds("key")
    assert data == {"equipment_tabs": []}
