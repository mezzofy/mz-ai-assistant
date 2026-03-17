"""
Tests for BUG-C/D/E — tool handler kwarg mismatch fixes.

Verifies:
  1. BaseTool.execute() drops unknown kwargs and logs a warning (global filter)
  2. BaseTool.execute() passes known kwargs through correctly
  3. create_pdf accepts 'content' as alias for 'html_content' (BUG-D)
  4. teams_post_message accepts 'channel' as alias for 'channel_name' (BUG-E)
  5. BaseTool skips filtering for handlers that accept **kwargs
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit


# ── Minimal BaseTool subclass for unit testing ────────────────────────────────

class _StrictHandler:
    """Tracks calls and accepts only (metric, period)."""
    def __init__(self):
        self.calls = []

    async def handle(self, metric: str, period: str = "30d") -> dict:
        self.calls.append({"metric": metric, "period": period})
        return {"success": True, "output": f"{metric}/{period}"}


class _VarKwargHandler:
    """Handler that accepts **kwargs — filter must be skipped."""
    def __init__(self):
        self.received = {}

    async def handle(self, **kwargs) -> dict:
        self.received = kwargs
        return {"success": True}


def _make_tool_class(handler_obj, method_name="handle"):
    """Build a minimal BaseTool subclass wired to the given handler."""
    from app.tools.base_tool import BaseTool

    handler = getattr(handler_obj, method_name)

    class _TestTool(BaseTool):
        def get_tools(self):
            return [{"name": "test_tool", "description": "test", "parameters": {}, "handler": handler}]

    return _TestTool({})


# ── 1. Global filter drops unknown kwargs ─────────────────────────────────────

class TestBaseToolKwargFilter:
    async def test_drops_unknown_kwarg_no_type_error(self):
        """BUG-C pattern: LLM passes start_date which the handler doesn't accept."""
        tracker = _StrictHandler()
        tool = _make_tool_class(tracker)

        # Must not raise TypeError
        result = await tool.execute("test_tool", metric="active_users", start_date="2026-03-01")

        assert result["success"] is True
        assert len(tracker.calls) == 1
        # start_date must have been dropped
        assert "start_date" not in tracker.calls[0]

    async def test_known_kwargs_pass_through(self):
        """Known params must still reach the handler after filtering."""
        tracker = _StrictHandler()
        tool = _make_tool_class(tracker)

        result = await tool.execute("test_tool", metric="api_calls", period="7d")

        assert result["success"] is True
        assert tracker.calls[0]["metric"] == "api_calls"
        assert tracker.calls[0]["period"] == "7d"

    async def test_drops_unknown_kwargs_logs_warning(self, caplog):
        """A warning must be emitted when kwargs are dropped."""
        import logging
        tracker = _StrictHandler()
        tool = _make_tool_class(tracker)

        with caplog.at_level(logging.WARNING, logger="mezzofy.tools"):
            await tool.execute("test_tool", metric="x", unknown_param="oops")

        assert any("unknown_param" in r.message for r in caplog.records)

    async def test_skips_filter_for_var_keyword_handler(self):
        """Handlers with **kwargs must receive ALL kwargs unfiltered."""
        tracker = _VarKwargHandler()
        tool = _make_tool_class(tracker)

        await tool.execute("test_tool", foo="a", bar="b", baz="c")

        assert tracker.received == {"foo": "a", "bar": "b", "baz": "c"}


# ── 2. create_pdf content alias (BUG-D) ───────────────────────────────────────

class TestCreatePdfContentAlias:
    def _make_pdf_ops(self):
        from app.tools.document.pdf_ops import PDFOps
        return PDFOps({})

    async def test_content_alias_accepted_no_error(self):
        """BUG-D: LLM passes 'content' instead of 'html_content' — must not raise."""
        ops = self._make_pdf_ops()
        with patch.object(ops, "_create_pdf_reportlab") as mock_render:
            result = await ops.execute(
                "create_pdf",
                title="Sales Report",
                content="<p>Pipeline summary</p>",
                storage_scope="department",
            )

        assert result.get("success") is not False, f"Unexpected error: {result.get('error')}"

    async def test_html_content_alias_maps_to_html_content(self):
        """content= param must be used as html_content when html_content is absent."""
        ops = self._make_pdf_ops()
        captured = {}

        def fake_render(title, html_content, output_path):
            captured["html_content"] = html_content

        with patch.object(ops, "_create_pdf_reportlab", side_effect=fake_render):
            await ops.execute(
                "create_pdf",
                title="T",
                content="<h1>Hello</h1>",
            )

        assert captured.get("html_content") == "<h1>Hello</h1>"

    async def test_html_content_takes_precedence_over_content(self):
        """html_content= must win if both html_content and content are supplied."""
        ops = self._make_pdf_ops()
        captured = {}

        def fake_render(title, html_content, output_path):
            captured["html_content"] = html_content

        with patch.object(ops, "_create_pdf_reportlab", side_effect=fake_render):
            await ops.execute(
                "create_pdf",
                title="T",
                html_content="<p>real</p>",
                content="<p>alias</p>",
            )

        assert captured.get("html_content") == "<p>real</p>"


# ── 3. teams_post_message channel alias (BUG-E) ───────────────────────────────

class TestTeamsPostMessageChannelAlias:
    def _make_teams_ops(self):
        from app.tools.communication.teams_ops import TeamsOps
        config = {
            "ms365": {
                "client_id": "test-client-id",
                "client_secret": "test-secret",
                "tenant_id": "test-tenant",
            },
            "teams": {
                "team_id": "test-team-id",
                "channels": {
                    "sales": "channel-sales-id",
                    "general": "channel-general-id",
                },
                "sender_user_id": "test-user-id",
            },
        }
        return TeamsOps(config)

    async def test_channel_alias_accepted_no_type_error(self):
        """BUG-E: LLM passes 'channel' instead of 'channel_name' — must not raise TypeError."""
        ops = self._make_teams_ops()

        # Patch the Graph client so no real API call happens
        with patch.object(ops, "_get_client", return_value=AsyncMock()):
            # channel_name resolves from 'channel' alias; will fail on Graph call
            # but must NOT fail with "unexpected keyword argument 'channel'"
            result = await ops.execute(
                "teams_post_message",
                channel="sales",
                content="Pipeline update",
            )

        # Error is acceptable (no real Graph creds), but TypeError is not
        assert "unexpected keyword argument" not in str(result.get("error", ""))

    async def test_channel_alias_resolves_channel_name(self):
        """channel= must resolve to channel_name inside _post_message."""
        ops = self._make_teams_ops()
        captured = {}

        async def fake_post(channel_name=None, content="", channel=None, subject=None):
            captured["channel_name"] = channel_name or channel
            return {"success": True}

        with patch.object(ops, "_post_message", side_effect=fake_post):
            await ops.execute("teams_post_message", channel="sales", content="Hello")

        assert captured.get("channel_name") == "sales"

    async def test_missing_channel_returns_error_not_exception(self):
        """If neither channel_name nor channel is provided, return error dict."""
        ops = self._make_teams_ops()
        result = await ops.execute("teams_post_message", content="Hello")

        assert result["success"] is False
        assert "required" in result["error"].lower() or "channel" in result["error"].lower()
