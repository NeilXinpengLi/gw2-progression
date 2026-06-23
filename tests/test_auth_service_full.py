"""Comprehensive tests for auth_service with mocked DB."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gw2_progression.services.auth_service import (
    cleanup_expired,
    create_session,
    delete_session,
    get_api_key,
    get_session,
    list_sessions,
)


def _fake_row(**kw):
    row = MagicMock()
    for k, v in kw.items():
        setattr(row, k, v)
    row.__getitem__ = lambda s, k: kw.get(k)
    return row


@pytest.fixture
def mock_db():
    db = AsyncMock()
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=None)
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.rowcount = 0
    db.execute = AsyncMock(return_value=cursor)
    db.commit = AsyncMock()
    return db


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_create_session_returns_token(self, mock_db):
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            token = await create_session("test-api-key", "Player.1234")
        assert len(token) == 48  # 24 bytes hex
        assert token.isalnum()

    @pytest.mark.asyncio
    async def test_create_session_calls_insert(self, mock_db):
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            await create_session("test-api-key", "Player.1234")
        insert_sql = mock_db.execute.call_args[0][0]
        assert "INSERT OR REPLACE INTO account_sessions" in insert_sql


class TestGetSession:
    @pytest.mark.asyncio
    async def test_get_session_returns_none_when_not_found(self, mock_db):
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            result = await get_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_returns_data_when_found(self, mock_db):
        import time
        from datetime import datetime, timezone

        now_ts = time.time()
        fake_created = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()
        mock_db.execute.return_value.fetchone = AsyncMock(
            return_value=_fake_row(api_key="test-api-key", account_name="Player.1234", created_at=fake_created)
        )
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            result = await get_session("valid-token")
        assert result is not None
        assert result["api_key"] == "test-api-key"

    @pytest.mark.asyncio
    async def test_get_session_expired_returns_none(self, mock_db):
        from datetime import datetime, timezone

        expired = datetime.fromtimestamp(0, tz=timezone.utc).isoformat()
        mock_db.execute.return_value.fetchone = AsyncMock(
            return_value=_fake_row(api_key="old-key", account_name="Old.Player", created_at=expired)
        )
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            result = await get_session("expired-token")
        assert result is None
        # Should have deleted the expired session
        delete_calls = [c for c in mock_db.execute.call_args_list if "DELETE" in str(c)]
        assert len(delete_calls) > 0


class TestGetApiKey:
    @pytest.mark.asyncio
    async def test_passthrough_short_string(self):
        key = await get_api_key("short")
        assert key == "short"

    @pytest.mark.asyncio
    async def test_passthrough_bearer(self):
        key = await get_api_key("Bearer some-token")
        assert key == "Bearer some-token"

    @pytest.mark.asyncio
    async def test_passthrough_normal_key(self):
        key = await get_api_key("ABCDEF01-2345-6789-ABCD-EF0123456789")
        assert key == "ABCDEF01-2345-6789-ABCD-EF0123456789"

    @pytest.mark.asyncio
    async def test_resolves_session_token(self, mock_db):
        mock_db.execute.return_value.fetchone = AsyncMock(
            return_value=_fake_row(api_key="resolved-key", account_name="Player.1234", created_at="2099-01-01T00:00:00")
        )
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            key = await get_api_key("a" * 48)
        assert key == "resolved-key"


class TestListSessions:
    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, mock_db):
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            sessions = await list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_list_sessions_with_data(self, mock_db):
        mock_db.execute.return_value.fetchall = AsyncMock(
            return_value=[
                _fake_row(token="abc123" * 6, account_name="Player.1", created_at="2025-01-01", last_used_at="2025-06-01"),
                _fake_row(token="def456" * 6, account_name="Player.2", created_at="2025-02-01", last_used_at="2025-06-15"),
            ]
        )
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            sessions = await list_sessions()
        assert len(sessions) == 2
        assert "..." in sessions[0]["token"]  # truncated

    @pytest.mark.asyncio
    async def test_list_sessions_filtered_by_account(self, mock_db):
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            await list_sessions(account_name="Player.1")
        call_args = mock_db.execute.call_args[0]
        assert "WHERE account_name = ?" in call_args[0]
        assert call_args[1][0] == "Player.1"


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_delete_session_returns_true(self, mock_db):
        mock_db.execute.return_value.rowcount = 1
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            result = await delete_session("valid-token")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_session_returns_false(self, mock_db):
        mock_db.execute.return_value.rowcount = 0
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            result = await delete_session("nonexistent")
        assert result is False


class TestCleanupExpired:
    @pytest.mark.asyncio
    async def test_cleanup_expired_runs(self, mock_db):
        with patch("gw2_progression.services.auth_service.get_db", AsyncMock(return_value=mock_db)), \
             patch("gw2_progression.services.auth_service.release_db", AsyncMock()):
            await cleanup_expired()
        call_args = mock_db.execute.call_args[0]
        assert "DELETE FROM account_sessions" in call_args[0]
        mock_db.commit.assert_called_once()
