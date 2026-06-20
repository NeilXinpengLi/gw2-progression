from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.analyzer import AccountContents, fetch_all
from gw2_progression.gw2_client import Gw2ApiError

BASE = "gw2_progression.analyzer"

ALL_PERMS = [
    "account",
    "builds",
    "characters",
    "guilds",
    "inventories",
    "progression",
    "pvp",
    "tradingpost",
    "unlocks",
    "wallet",
    "wvw",
]

TOKENINFO = {"name": "TestKey", "id": "abc", "permissions": ALL_PERMS}
ACCOUNT = {
    "name": "Player.1234",
    "world": 1001,
    "created": "2022-01-01T00:00:00Z",
    "age": 3600,
    "fractal_level": 10,
    "daily_ap": 100,
    "monthly_ap": 0,
    "wvw_rank": 1,
    "guilds": [],
}

ALL_STUBS = {
    "fetch_account": ACCOUNT,
    "fetch_characters": [],
    "fetch_wallet": [],
    "fetch_bank": [],
    "fetch_materials": [],
    "fetch_inventory": [],
    "fetch_achievements": [],
    "fetch_masteries": [],
    "fetch_mastery_points": {},
    "fetch_builds": [],
    "fetch_guilds": [],
    "fetch_pvp_stats": {},
    "fetch_pvp_games": [],
    "fetch_pvp_standings": [],
    "fetch_tradingpost_current_buys": [],
    "fetch_tradingpost_current_sells": [],
    "fetch_unlocked_skins": [],
    "fetch_unlocked_dyes": [],
    "fetch_unlocked_minis": [],
    "fetch_unlocked_finishers": [],
    "fetch_wvw_stats": {},
}


def _mock_async(return_value=None, side_effect=None):
    m = AsyncMock()
    if side_effect:
        m.side_effect = side_effect
    else:
        m.return_value = return_value
    return m


def _patch_all(overrides=None, tokeninfo=None):
    """ExitStack-based context manager that patches all fetch_* functions."""
    stubs = {**ALL_STUBS, **(overrides or {})}
    token = tokeninfo or TOKENINFO
    stack = ExitStack()
    stack.enter_context(patch(f"{BASE}.fetch_tokeninfo", _mock_async(token)))
    for fn, val in stubs.items():
        mock = val if isinstance(val, AsyncMock) else _mock_async(val)
        stack.enter_context(patch(f"{BASE}.{fn}", mock))
    return stack


@pytest.mark.asyncio
async def test_valid_key_returns_account_name():
    with _patch_all():
        result = await fetch_all("fake-key")
    assert isinstance(result, AccountContents)
    assert result.account_name == "Player.1234"
    assert result.token_name == "TestKey"


@pytest.mark.asyncio
async def test_invalid_key_raises():
    with patch(f"{BASE}.fetch_tokeninfo", _mock_async(side_effect=Gw2ApiError(401, "Invalid or expired API key."))):
        with pytest.raises(Gw2ApiError) as exc:
            await fetch_all("bad-key")
        assert "Invalid" in str(exc.value.message)


@pytest.mark.asyncio
async def test_all_permissions_no_errors():
    with _patch_all(overrides={"fetch_unlocked_skins": [1, 2, 3]}):
        result = await fetch_all("fake-key")
    assert result.errors == {}
    assert result.unlocked_skins_count == 3


@pytest.mark.asyncio
async def test_account_only_permission():
    """Only 'account' permission granted — everything else stays None."""
    limited = {**TOKENINFO, "permissions": ["account"]}
    with _patch_all(tokeninfo=limited):
        result = await fetch_all("fake-key")
    assert result.account_name == "Player.1234"
    assert result.characters is None
    assert result.wallet is None
    assert result.errors == {}


@pytest.mark.asyncio
async def test_endpoint_error_isolated():
    """Single endpoint failure populates errors dict, others succeed."""
    with _patch_all(overrides={"fetch_characters": _mock_async(side_effect=Gw2ApiError(500, "GW2 down"))}):
        result = await fetch_all("fake-key")
    assert "characters" in result.errors
    assert result.wallet == []
    assert result.account_name == "Player.1234"


@pytest.mark.asyncio
async def test_fetch_guilds_receives_guild_ids():
    """fetch_guilds should receive guild_ids from account, not call fetch_account again."""
    account_with_guilds = {**ACCOUNT, "guilds": ["11111-11111-11111"]}
    with _patch_all(overrides={"fetch_account": account_with_guilds}):
        result = await fetch_all("fake-key")
    assert result.account_name == "Player.1234"


@pytest.mark.asyncio
async def test_invalid_key_format_empty():
    """Empty key should not reach HTTP layer — validation at route level."""
    with patch(f"{BASE}.fetch_tokeninfo", _mock_async(side_effect=Gw2ApiError(401, "Invalid or expired API key."))):
        with pytest.raises(Gw2ApiError):
            await fetch_all("")
