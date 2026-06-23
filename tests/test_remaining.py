"""Comprehensive tests for remaining uncovered services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _ac(fetch=None, fetchall=None, lastrowid=1):
    c = MagicMock()
    c.lastrowid = lastrowid
    c.fetchone = AsyncMock(return_value=fetch)
    c.fetchall = AsyncMock(return_value=fetchall or [])
    return c


# ── Agent Service Tests ──


class TestAgentService:
    @pytest.mark.asyncio
    async def test_parse_llm_response_plain(self):
        from gw2_progression.services.agent_service import _parse_llm_response

        result = _parse_llm_response('{"summary": "test", "recommended_actions": []}')
        assert result["summary"] == "test"

    @pytest.mark.asyncio
    async def test_parse_llm_response_code_fence(self):
        from gw2_progression.services.agent_service import _parse_llm_response

        result = _parse_llm_response('```json\n{"summary": "fenced"}\n```')
        assert result["summary"] == "fenced"

    @pytest.mark.asyncio
    async def test_parse_llm_response_invalid(self):
        from gw2_progression.services.agent_service import _parse_llm_response

        result = _parse_llm_response("not json")
        assert result is None

    @pytest.mark.asyncio
    async def test_call_llm_no_key(self):
        from gw2_progression.services.agent_service import _call_llm

        with patch("gw2_progression.services.agent_service.LLM_API_KEY", None):
            result = await _call_llm("prompt")
        assert result is None

    @pytest.mark.asyncio
    async def test_call_llm_openai_success(self):
        from gw2_progression.services.agent_service import _call_llm

        with (
            patch("gw2_progression.services.agent_service.LLM_API_KEY", "sk-test"),
            patch("gw2_progression.services.agent_service.LLM_PROVIDER", "openai"),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"choices": [{"message": {"content": '{"summary": "ok"}'}}]}
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _call_llm("prompt")
        assert result["summary"] == "ok"

    @pytest.mark.asyncio
    async def test_call_llm_anthropic_success(self):
        from gw2_progression.services.agent_service import _call_llm

        with (
            patch("gw2_progression.services.agent_service.LLM_API_KEY", "sk-ant-test"),
            patch("gw2_progression.services.agent_service.LLM_PROVIDER", "anthropic"),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"content": [{"text": '{"summary": "claude ok"}'}]}
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _call_llm("prompt")
        assert result["summary"] == "claude ok"

    @pytest.mark.asyncio
    async def test_call_llm_api_error(self):
        from gw2_progression.services.agent_service import _call_llm

        with (
            patch("gw2_progression.services.agent_service.LLM_API_KEY", "sk-test"),
            patch("gw2_progression.services.agent_service.LLM_PROVIDER", "openai"),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _call_llm("prompt")
        assert result is None

    @pytest.mark.asyncio
    async def test_call_llm_credential_key(self):
        from gw2_progression.services.agent_service import _call_llm

        with (
            patch("gw2_progression.services.agent_service.LLM_API_KEY", None),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"choices": [{"message": {"content": '{"summary": "byok"}'}}]}
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _call_llm("prompt", credential_key="sk-byok", credential_provider="openai")
        assert result["summary"] == "byok"


# ── Provider Service Tests ──


@pytest.mark.asyncio
async def test_list_providers():
    from gw2_progression.services.provider_service import list_providers

    with patch("gw2_progression.database.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _ac(
            fetchall=[
                ("gw2", "game", "GW2 API", "api_key", "account,characters", "free", 1),
            ]
        )
        mock_db.return_value.__aenter__.return_value = mock_conn

        providers = await list_providers()
    assert len(providers) >= 1
    assert providers[0]["id"] == "gw2"


@pytest.mark.asyncio
async def test_list_providers_by_category():
    from gw2_progression.services.provider_service import list_providers

    with patch("gw2_progression.services.provider_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _ac(
            fetchall=[
                ("openai", "llm", "OpenAI", "api_key", "chat,completion", "token_based", 1),
            ]
        )
        mock_db.return_value.__aenter__.return_value = mock_conn

        providers = await list_providers("llm")
    assert len(providers) == 1
    assert providers[0]["category"] == "llm"


# ── Guild Aggregate Tests ──


@pytest.mark.asyncio
async def test_aggregate_guild():
    from gw2_progression.services.guild_aggregate import aggregate_guild

    with (
        patch("gw2_progression.services.guild_aggregate.get_member_accounts") as mock_members,
        patch("gw2_progression.services.guild_aggregate.fetch_all") as mock_fetch,
    ):
        mock_members.return_value = ["Player.One", "Player.Two"]
        mock_fetch.return_value.account_name = "Player"
        mock_fetch.return_value.wallet = [{"id": 1, "value": 100000}]
        mock_fetch.return_value.characters = [{"name": "War", "profession": "Warrior", "level": 80}]
        mock_fetch.return_value.unlocked_skins_count = 100
        mock_fetch.return_value.errors = {}

        result = await aggregate_guild(1)

    assert result["member_count"] == 2


# ── Progression Service Tests ──


@pytest.mark.asyncio
async def test_get_templates_returns_curated():
    from gw2_progression.services.progression_service import get_templates

    with patch("gw2_progression.services.progression_service.CURATED_TEMPLATES", [MagicMock(template_id="test")]):
        templates = await get_templates()
    assert len(templates) >= 1


# ── Snapshot Service Tests ──


@pytest.mark.asyncio
async def test_load_value_history_empty():
    from gw2_progression.database import load_value_history

    mock_db = AsyncMock()
    mock_db.execute.return_value = _ac(fetchall=[])
    history = await load_value_history(mock_db, "Player.Test", 5)
    assert history == []


# ── Price Quality Tests ──


def test_compute_price_quality():
    from gw2_progression.services.price_service import compute_price_quality

    result = compute_price_quality(0, 0, 0, 0)
    assert result is not None
    assert result["quality_status"] == "illiquid"

    result = compute_price_quality(100, 120, 500, 500)
    assert result is not None
    assert result["liquidity_score"] in ("high", "medium")
