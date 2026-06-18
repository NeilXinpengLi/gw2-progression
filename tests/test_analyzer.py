from contextlib import ExitStack
from unittest.mock import patch

from gw2_progression.analyzer import AccountContents, fetch_all
from gw2_progression.gw2_client import Gw2ApiError

BASE = "gw2_progression.analyzer"

ALL_PERMS = ["account", "builds", "characters", "guilds", "inventories",
             "progression", "pvp", "tradingpost", "unlocks", "wallet", "wvw"]

TOKENINFO = {"name": "TestKey", "id": "abc", "permissions": ALL_PERMS}
ACCOUNT   = {"name": "Player.1234", "world": 1001, "created": "2022-01-01T00:00:00Z",
             "age": 3600, "fractal_level": 10, "daily_ap": 100, "monthly_ap": 0,
             "wvw_rank": 1, "guilds": []}

STUBS = {
    "fetch_account":                   ACCOUNT,
    "fetch_characters":                [],
    "fetch_wallet":                    [],
    "fetch_bank":                      [],
    "fetch_materials":                 [],
    "fetch_inventory":                 [],
    "fetch_achievements":              [],
    "fetch_masteries":                 [],
    "fetch_mastery_points":            {},
    "fetch_builds":                    [],
    "fetch_guilds":                    [],
    "fetch_pvp_stats":                 {},
    "fetch_pvp_games":                 [],
    "fetch_pvp_standings":             [],
    "fetch_tradingpost_current_buys":  [],
    "fetch_tradingpost_current_sells": [],
    "fetch_unlocked_skins":            [],
    "fetch_unlocked_dyes":             [],
    "fetch_unlocked_minis":            [],
    "fetch_unlocked_finishers":        [],
    "fetch_wvw_stats":                 {},
}


def run_with_stubs(api_key="fake-key", tokeninfo=None, overrides=None):
    stubs = {**STUBS, **(overrides or {})}
    with ExitStack() as stack:
        stack.enter_context(patch(f"{BASE}.fetch_tokeninfo", return_value=tokeninfo or TOKENINFO))
        for fn, val in stubs.items():
            stack.enter_context(patch(f"{BASE}.{fn}", return_value=val))
        return fetch_all(api_key)


def test_valid_key_returns_account_name():
    result = run_with_stubs()
    assert isinstance(result, AccountContents)
    assert result.account_name == "Player.1234"
    assert result.token_name == "TestKey"


def test_invalid_key_raises():
    with patch(f"{BASE}.fetch_tokeninfo", side_effect=Gw2ApiError(401, "Invalid or expired API key.")):
        try:
            fetch_all("bad-key")
            assert False, "should have raised"
        except Gw2ApiError as e:
            assert "Invalid" in e.message


def test_all_permissions_no_errors():
    result = run_with_stubs(overrides={"fetch_unlocked_skins": [1, 2, 3]})
    assert result.errors == {}
    assert result.unlocked_skins_count == 3
