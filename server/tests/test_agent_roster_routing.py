"""
Agent Persona Map, Team Roster, and Persona Routing tests.

Tests cover:
  1.  _AGENT_PERSONA_MAP — all 10 departments map to correct persona names
  2.  _build_system_prompt() — includes self-identity + roster header
  3.  _detect_persona_routing() — name prefix and directed-phrase patterns
  4.  _detect_agent_type() — persona routing has highest priority
"""

import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import TEST_CONFIG

pytestmark = pytest.mark.unit


# ── Helper: construct LLMManager with mocked clients ──────────────────────────

def _get_llm_manager():
    """Return an LLMManager instance with all external clients mocked."""
    from app.llm.llm_manager import LLMManager
    with patch("app.llm.llm_manager.AnthropicClient") as mock_claude_cls, \
         patch("app.llm.llm_manager.KimiClient") as mock_kimi_cls, \
         patch("app.llm.llm_manager.ToolExecutor"):
        mock_claude = MagicMock()
        mock_claude.model_name = "claude-sonnet-4-6"
        mock_kimi = MagicMock()
        mock_kimi.model_name = "moonshot-v1-128k"
        mock_claude_cls.return_value = mock_claude
        mock_kimi_cls.return_value = mock_kimi
        manager = LLMManager(TEST_CONFIG)
    return manager


def _minimal_task(department: str) -> dict:
    """Minimal task dict sufficient to exercise _build_system_prompt()."""
    return {
        "department": department,
        "role": "user",
        "source": "mobile",
        "user_id": "u1",
    }


# ── Class 1: _AGENT_PERSONA_MAP ───────────────────────────────────────────────

class TestAgentPersonaMap:
    """Verify every department maps to the expected persona name."""

    def _get_map(self):
        from app.llm.llm_manager import _AGENT_PERSONA_MAP
        return _AGENT_PERSONA_MAP

    def test_management_maps_to_max(self):
        assert self._get_map()["management"] == "Max"

    def test_finance_maps_to_fiona(self):
        assert self._get_map()["finance"] == "Fiona"

    def test_sales_maps_to_sam(self):
        assert self._get_map()["sales"] == "Sam"

    def test_marketing_maps_to_maya(self):
        assert self._get_map()["marketing"] == "Maya"

    def test_support_maps_to_suki(self):
        assert self._get_map()["support"] == "Suki"

    def test_hr_maps_to_hana(self):
        assert self._get_map()["hr"] == "Hana"

    def test_legal_maps_to_leo(self):
        assert self._get_map()["legal"] == "Leo"

    def test_research_maps_to_rex(self):
        assert self._get_map()["research"] == "Rex"

    def test_developer_maps_to_dev(self):
        assert self._get_map()["developer"] == "Dev"

    def test_scheduler_maps_to_sched(self):
        assert self._get_map()["scheduler"] == "Sched"

    def test_unknown_dept_fallback(self):
        persona_map = self._get_map()
        assert persona_map.get("nonexistent", "AI Assistant") == "AI Assistant"

    def test_map_has_exactly_10_entries(self):
        assert len(self._get_map()) == 10


# ── Class 2: _build_system_prompt() ──────────────────────────────────────────

class TestSystemPromptRoster:
    """Verify _build_system_prompt() prepends self-identity + roster to every prompt."""

    def _build(self, department: str) -> str:
        manager = _get_llm_manager()
        return manager._build_system_prompt(_minimal_task(department))

    def test_finance_contains_fiona_identity(self):
        prompt = self._build("finance")
        assert "You are **Fiona**" in prompt

    def test_legal_contains_leo_identity(self):
        prompt = self._build("legal")
        assert "You are **Leo**" in prompt

    def test_hr_contains_hana_identity(self):
        prompt = self._build("hr")
        assert "You are **Hana**" in prompt

    def test_research_contains_rex_identity(self):
        prompt = self._build("research")
        assert "You are **Rex**" in prompt

    def test_management_contains_max_identity(self):
        prompt = self._build("management")
        assert "You are **Max**" in prompt

    def test_sales_contains_sam_identity(self):
        prompt = self._build("sales")
        assert "You are **Sam**" in prompt

    def test_marketing_contains_maya_identity(self):
        prompt = self._build("marketing")
        assert "You are **Maya**" in prompt

    def test_support_contains_suki_identity(self):
        prompt = self._build("support")
        assert "You are **Suki**" in prompt

    def test_developer_contains_dev_identity(self):
        prompt = self._build("developer")
        assert "You are **Dev**" in prompt

    def test_scheduler_contains_sched_identity(self):
        prompt = self._build("scheduler")
        assert "You are **Sched**" in prompt

    def test_roster_header_present(self):
        prompt = self._build("finance")
        assert "Mezzofy AI Team" in prompt

    def test_all_10_persona_names_in_roster(self):
        prompt = self._build("finance")
        for name in ("Max", "Fiona", "Sam", "Maya", "Suki", "Hana", "Leo", "Rex", "Dev", "Sched"):
            assert name in prompt, f"Expected persona '{name}' in system prompt"

    def test_roster_appears_before_template_content(self):
        """Self-identity + roster must be prepended — roster index < template content index."""
        prompt = self._build("finance")
        roster_pos = prompt.index("Mezzofy AI Team")
        # The base template always contains department-specific text
        # Find some template marker that appears after the roster
        identity_pos = prompt.index("You are **Fiona**")
        assert identity_pos < roster_pos, "Self-identity should precede the full roster table"
        # Verify roster precedes the main body (which contains the save_options prompt)
        save_options_pos = prompt.index("Where would you like to save")
        assert roster_pos < save_options_pos, "Roster should appear before save-options template content"

    def test_custom_system_prompt_bypasses_roster(self):
        """task['system_prompt'] is returned as-is — no roster injection."""
        manager = _get_llm_manager()
        task = {"system_prompt": "Custom override prompt"}
        prompt = manager._build_system_prompt(task)
        assert prompt == "Custom override prompt"
        assert "Mezzofy AI Team" not in prompt


# ── Class 3: _detect_persona_routing() ───────────────────────────────────────

class TestPersonaRouting:
    """Unit tests for _detect_persona_routing() in app.api.chat."""

    def _detect(self, message: str):
        from app.api.chat import _detect_persona_routing
        return _detect_persona_routing(message)

    # -- Name prefix syntax: "persona: message" --

    def test_leo_prefix_routes_to_legal(self):
        assert self._detect("leo: review this NDA") == "legal"

    def test_rex_prefix_routes_to_research(self):
        assert self._detect("rex: research our competitors") == "research"

    def test_dev_prefix_routes_to_developer(self):
        assert self._detect("dev: write a python script") == "developer"

    def test_sched_prefix_routes_to_scheduler(self):
        assert self._detect("sched: create a daily job") == "scheduler"

    def test_max_prefix_routes_to_management(self):
        assert self._detect("max: run KPI dashboard") == "management"

    def test_fiona_prefix_routes_to_finance(self):
        assert self._detect("fiona: generate Q1 report") == "finance"

    def test_sam_prefix_routes_to_sales(self):
        assert self._detect("sam: find sales leads") == "sales"

    def test_maya_prefix_routes_to_marketing(self):
        assert self._detect("maya: write a blog post") == "marketing"

    def test_suki_prefix_routes_to_support(self):
        assert self._detect("suki: check open tickets") == "support"

    def test_hana_prefix_routes_to_hr(self):
        assert self._detect("hana: show leave report") == "hr"

    # -- Directed phrase: "ask/route to/have/talk to <name> ..." --

    def test_ask_leo_routes_to_legal(self):
        assert self._detect("ask Leo to review this contract") == "legal"

    def test_route_to_rex_routes_to_research(self):
        assert self._detect("route to Rex") == "research"

    def test_have_sam_routes_to_sales(self):
        assert self._detect("have Sam find some leads") == "sales"

    def test_talk_to_fiona_routes_to_finance(self):
        assert self._detect("talk to Fiona about our finances") == "finance"

    def test_ask_max_routes_to_management(self):
        assert self._detect("ask Max to run a report") == "management"

    # -- False-positive safety tests — must return None --

    def test_max_in_sentence_no_prefix_returns_none(self):
        assert self._detect("the max items in the list") is None

    def test_dev_word_no_colon_returns_none(self):
        assert self._detect("dev environment setup") is None

    def test_sam_subject_no_verb_returns_none(self):
        assert self._detect("sam is working on it") is None

    def test_empty_string_returns_none(self):
        assert self._detect("") is None

    def test_generic_message_returns_none(self):
        assert self._detect("what is the weather today?") is None


# ── Class 4: _detect_agent_type() with persona routing priority ───────────────

class TestDetectAgentTypeWithPersona:
    """Verify _detect_agent_type() uses persona routing as highest priority."""

    def _detect(self, message: str):
        from app.api.chat import _detect_agent_type
        return _detect_agent_type(message)

    # -- Persona prefix beats everything --

    def test_leo_prefix_beats_other_routing(self):
        assert self._detect("leo: do this") == "legal"

    def test_ask_rex_directed_phrase(self):
        assert self._detect("ask rex to research") == "research"

    def test_route_to_sam_directed_phrase(self):
        assert self._detect("route to sam") == "sales"

    # -- Existing prefix routing still works --

    def test_research_prefix_still_works(self):
        assert self._detect("research: find something") == "research"

    # -- Existing keyword routing still works --

    def test_legal_keyword_still_works(self):
        assert self._detect("draft a contract") == "legal"

    def test_developer_keyword_still_works(self):
        assert self._detect("write a python script") == "developer"

    # -- No match --

    def test_unrecognised_message_returns_none(self):
        assert self._detect("hello there") is None
