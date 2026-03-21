"""
BaseAgent._general_response() unit tests.

Tests cover the new chat_with_memory-first behavior introduced in the backend
refactor where _general_response() was updated to:
  1. Call chat_with_memory() and return tools_called=["memory"] on success.
  2. Fall back to execute_with_tools() when chat_with_memory() raises.

Also verifies that SalesAgent._general_sales_workflow() delegates to
_general_response() (and thereby reaches chat_with_memory) instead of calling
execute_with_tools() directly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_CONFIG

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────────────────

def _base_task(message="hello", user_id="user-abc", department="management"):
    return {
        "message": message,
        "user_id": user_id,
        "department": department,
        "source": "mobile",
        "conversation_history": [],
    }


def _make_management_agent():
    from app.agents.management_agent import ManagementAgent
    return ManagementAgent(TEST_CONFIG)


def _make_sales_agent():
    from app.agents.sales_agent import SalesAgent
    return SalesAgent(TEST_CONFIG)


# ── BaseAgent._general_response: success path (chat_with_memory) ───────────────

class TestGeneralResponseSuccessPath:

    @pytest.mark.asyncio
    async def test_chat_with_memory_called_on_success(self):
        """_general_response calls chat_with_memory and returns tools_called=['memory']."""
        agent = _make_management_agent()
        task = _base_task()

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="system-prompt")
        mock_llm.chat_with_memory = AsyncMock(
            return_value={"text": "Memory response", "tools_called": []}
        )
        mock_llm.execute_with_tools = AsyncMock()

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        mock_llm.chat_with_memory.assert_called_once()
        mock_llm.execute_with_tools.assert_not_called()
        assert result["success"] is True
        assert result["tools_called"] == ["memory"]

    @pytest.mark.asyncio
    async def test_success_path_returns_text_content(self):
        """_general_response extracts 'text' field from chat_with_memory result."""
        agent = _make_management_agent()
        task = _base_task(message="What is our pipeline?")

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(
            return_value={"text": "Pipeline is strong.", "tools_called": []}
        )

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        assert result["content"] == "Pipeline is strong."

    @pytest.mark.asyncio
    async def test_success_path_falls_back_to_content_key_when_text_absent(self):
        """_general_response accepts 'content' key if 'text' is missing or empty."""
        agent = _make_management_agent()
        task = _base_task()

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(
            return_value={"content": "Content key response", "text": ""}
        )

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        assert result["content"] == "Content key response"

    @pytest.mark.asyncio
    async def test_success_path_memory_scope_uses_user_id(self):
        """chat_with_memory is called with memory_scope='user:{user_id}'."""
        agent = _make_management_agent()
        task = _base_task(user_id="user-xyz-42")

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(
            return_value={"text": "ok", "tools_called": []}
        )

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            await agent._general_response(task)

        call_kwargs = mock_llm.chat_with_memory.call_args[1]
        assert call_kwargs.get("memory_scope") == "user:user-xyz-42"

    @pytest.mark.asyncio
    async def test_empty_response_replaced_with_default_message(self):
        """When chat_with_memory returns empty text, a default help message is used."""
        agent = _make_management_agent()
        task = _base_task()

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(
            return_value={"text": "", "content": ""}
        )

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        assert result["content"]  # must not be empty
        assert result["success"] is True
        assert result["tools_called"] == ["memory"]


# ── BaseAgent._general_response: fallback path (execute_with_tools) ────────────

class TestGeneralResponseFallbackPath:

    @pytest.mark.asyncio
    async def test_execute_with_tools_called_when_chat_with_memory_raises(self):
        """When chat_with_memory raises, execute_with_tools is called as fallback."""
        agent = _make_management_agent()
        task = _base_task()

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(side_effect=Exception("memory tool failed"))
        mock_llm.execute_with_tools = AsyncMock(
            return_value={"content": "Fallback response", "tools_called": ["search"], "artifacts": []}
        )

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        mock_llm.chat_with_memory.assert_called_once()
        mock_llm.execute_with_tools.assert_called_once()
        assert result["success"] is True
        assert result["content"] == "Fallback response"

    @pytest.mark.asyncio
    async def test_fallback_returns_tools_from_execute_with_tools(self):
        """Fallback path propagates tools_called from execute_with_tools result."""
        agent = _make_management_agent()
        task = _base_task()

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(side_effect=RuntimeError("unavailable"))
        mock_llm.execute_with_tools = AsyncMock(
            return_value={
                "content": "Tool response",
                "tools_called": ["db_query", "send_email"],
                "artifacts": [],
            }
        )

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        assert result["tools_called"] == ["db_query", "send_email"]

    @pytest.mark.asyncio
    async def test_fallback_does_not_include_memory_in_tools_called(self):
        """Fallback path must NOT include 'memory' in tools_called."""
        agent = _make_management_agent()
        task = _base_task()

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(side_effect=Exception("fail"))
        mock_llm.execute_with_tools = AsyncMock(
            return_value={"content": "ok", "tools_called": [], "artifacts": []}
        )

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        assert "memory" not in result["tools_called"]


# ── SalesAgent._general_sales_workflow delegates to _general_response ──────────

class TestSalesAgentGeneralWorkflow:

    @pytest.mark.asyncio
    async def test_general_sales_workflow_delegates_to_general_response(self):
        """_general_sales_workflow() must call self._general_response(task)."""
        agent = _make_sales_agent()
        task = _base_task(message="what is our Q1 revenue target?", department="sales")

        canned = {
            "success": True,
            "content": "Q1 target is $2M",
            "tools_called": ["memory"],
            "artifacts": [],
        }

        with patch.object(agent, "_general_response", new_callable=AsyncMock,
                          return_value=canned) as mock_gr:
            result = await agent._general_sales_workflow(task)

        mock_gr.assert_called_once_with(task)
        assert result == canned

    @pytest.mark.asyncio
    async def test_general_sales_workflow_reaches_chat_with_memory(self):
        """Unrecognised sales message reaches chat_with_memory via _general_sales_workflow."""
        agent = _make_sales_agent()
        task = _base_task(message="what is our Q1 revenue target?", department="sales")

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(
            return_value={"text": "Revenue target is $2M", "tools_called": []}
        )
        mock_llm.execute_with_tools = AsyncMock()

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_sales_workflow(task)

        mock_llm.chat_with_memory.assert_called_once()
        mock_llm.execute_with_tools.assert_not_called()
        assert result["tools_called"] == ["memory"]

    @pytest.mark.asyncio
    async def test_execute_unknown_message_routes_to_general_response_via_sales_workflow(self):
        """SalesAgent.execute() with unknown message calls _general_sales_workflow
        which delegates to _general_response (and thereby chat_with_memory)."""
        agent = _make_sales_agent()
        task = {
            **_base_task(message="what is our Q1 revenue target?", department="sales"),
            "user_id": "user-sales-1",
        }

        mock_llm = MagicMock()
        mock_llm._build_system_prompt = MagicMock(return_value="")
        mock_llm.chat_with_memory = AsyncMock(
            return_value={"text": "Revenue target is $2M", "tools_called": []}
        )

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent.execute(task)

        mock_llm.chat_with_memory.assert_called_once()
        assert result["success"] is True
        assert result["tools_called"] == ["memory"]


# ── ManagementAgent inherits _general_response (no override) ──────────────────

class TestManagementAgentInheritsGeneralResponse:

    def test_management_agent_has_no_general_response_override(self):
        """ManagementAgent must NOT define its own _general_response method."""
        from app.agents.management_agent import ManagementAgent
        from app.agents.base_agent import BaseAgent

        # If ManagementAgent defines _general_response in its own __dict__,
        # that means the override still exists — which contradicts the refactor.
        assert "_general_response" not in ManagementAgent.__dict__, (
            "ManagementAgent still has its own _general_response override — "
            "it should inherit from BaseAgent after the refactor."
        )

    def test_management_agent_general_response_is_base_agent_method(self):
        """ManagementAgent._general_response is BaseAgent's implementation."""
        from app.agents.management_agent import ManagementAgent
        from app.agents.base_agent import BaseAgent

        agent = ManagementAgent(TEST_CONFIG)
        assert agent._general_response.__func__ is BaseAgent._general_response
