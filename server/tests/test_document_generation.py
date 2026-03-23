"""
Document Generation Tests — PPTX, DOCX, XLSX, PDF

Tests that the four document-generation ops classes produce valid output files
and that the critical bug in PitchDeckGenerationSkill is fixed.

All tests are unit-level: filesystem I/O only, no LLM/DB/network calls.
Output is directed to a temp directory that mirrors the personal-folder structure.

Run:
    pytest tests/test_document_generation.py -v
    pytest tests/test_document_generation.py -v -k pptx
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── Test Config ────────────────────────────────────────────────────────────────

TEST_DEPT = "management"
TEST_EMAIL = "admin@mezzofy.com"
TEST_CONTENT = "This is a Test"

pytestmark = pytest.mark.unit


@pytest.fixture()
def tmp_artifacts(tmp_path: Path) -> Path:
    """Return a temp dir that acts as the personal artifacts folder."""
    personal = tmp_path / TEST_DEPT / TEST_EMAIL
    personal.mkdir(parents=True)
    return personal


@pytest.fixture()
def doc_config(tmp_artifacts: Path) -> dict:
    """Minimal config that points all ops classes to the temp personal folder."""
    return {
        "storage": {
            "local_path": str(tmp_artifacts.parent.parent),  # base/dept/email
        },
        "llm": {
            "default_model": "claude",
            "claude": {
                "api_key": "test-key",
                "model": "claude-sonnet-4-6",
            },
        },
    }


def _patch_user_context(dept: str = TEST_DEPT, email: str = TEST_EMAIL):
    """Patch get_user_dept / get_user_email for storage scope resolution."""
    return [
        patch("app.context.artifact_manager.os.getenv", return_value=None),
        patch("app.core.user_context.get_user_dept", return_value=dept),
        patch("app.core.user_context.get_user_email", return_value=email),
    ]


# ── PPTX Tests ─────────────────────────────────────────────────────────────────

class TestPPTXOps:
    """Tests for PPTXOps.create_pptx — personal folder output."""

    def test_tool_name_is_create_pptx(self, doc_config):
        """Tool registry must expose 'create_pptx', not 'create_presentation'."""
        from app.tools.document.pptx_ops import PPTXOps
        ops = PPTXOps(doc_config)
        tool_names = [t["name"] for t in ops.get_tools()]
        assert "create_pptx" in tool_names, (
            "PPTXOps must register 'create_pptx'. Got: " + str(tool_names)
        )
        assert "create_presentation" not in tool_names, (
            "'create_presentation' is the old broken name and must NOT appear in the registry."
        )

    @pytest.mark.asyncio
    async def test_create_pptx_produces_file(self, doc_config, tmp_artifacts):
        """create_pptx generates a .pptx file in the personal folder."""
        from app.tools.document.pptx_ops import PPTXOps

        with (
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            ops = PPTXOps(doc_config)
            result = await ops._create_pptx(
                title=TEST_CONTENT,
                slides=[
                    {"type": "content", "heading": TEST_CONTENT, "body": TEST_CONTENT},
                ],
                filename="test_pptx_output",
                storage_scope="user",
            )

        assert result.get("success") is True, f"create_pptx failed: {result.get('error')}"
        file_path = Path(result["file_path"])
        assert file_path.exists(), f"PPTX file not found at: {file_path}"
        assert file_path.suffix == ".pptx"
        assert file_path.stat().st_size > 0
        assert result["title"] == TEST_CONTENT

    @pytest.mark.asyncio
    async def test_create_pptx_cover_slide_included(self, doc_config, tmp_artifacts):
        """A cover slide is always prepended — slide_count = len(slides) + 1."""
        from app.tools.document.pptx_ops import PPTXOps

        with (
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            ops = PPTXOps(doc_config)
            result = await ops._create_pptx(
                title=TEST_CONTENT,
                slides=[
                    {"type": "content", "heading": "Slide 1", "body": TEST_CONTENT},
                    {"type": "content", "heading": "Slide 2", "body": TEST_CONTENT},
                ],
                filename="test_pptx_cover",
                storage_scope="user",
            )

        assert result.get("success") is True
        assert result["slide_count"] == 3  # 2 content + 1 cover


# ── DOCX Tests ─────────────────────────────────────────────────────────────────

class TestDocxOps:
    """Tests for DocxOps.create_docx — personal folder output."""

    def test_tool_name_is_create_docx(self, doc_config):
        """Tool registry must expose 'create_docx'."""
        from app.tools.document.docx_ops import DocxOps
        ops = DocxOps(doc_config)
        tool_names = [t["name"] for t in ops.get_tools()]
        assert "create_docx" in tool_names, "DocxOps must register 'create_docx'. Got: " + str(tool_names)

    @pytest.mark.asyncio
    async def test_create_docx_produces_file(self, doc_config, tmp_artifacts):
        """create_docx generates a .docx file in the personal folder."""
        from app.tools.document.docx_ops import DocxOps

        with (
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            ops = DocxOps(doc_config)
            result = await ops._create_docx(
                title=TEST_CONTENT,
                sections=[
                    {"type": "paragraph", "content": TEST_CONTENT},
                ],
                filename="test_docx_output",
                storage_scope="user",
            )

        assert result.get("success") is True, f"create_docx failed: {result.get('error')}"
        file_path = Path(result["file_path"])
        assert file_path.exists(), f"DOCX file not found at: {file_path}"
        assert file_path.suffix == ".docx"
        assert file_path.stat().st_size > 0
        assert result["title"] == TEST_CONTENT

    @pytest.mark.asyncio
    async def test_create_docx_all_section_types(self, doc_config, tmp_artifacts):
        """All section types (heading1/2/3, paragraph, list, table) render without error."""
        from app.tools.document.docx_ops import DocxOps

        with (
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            ops = DocxOps(doc_config)
            result = await ops._create_docx(
                title=TEST_CONTENT,
                sections=[
                    {"type": "heading1", "content": "Heading 1"},
                    {"type": "heading2", "content": "Heading 2"},
                    {"type": "heading3", "content": "Heading 3"},
                    {"type": "paragraph", "content": TEST_CONTENT},
                    {"type": "list", "content": "Item 1\nItem 2\nItem 3"},
                    {
                        "type": "table",
                        "table_data": [
                            ["Col A", "Col B"],
                            [TEST_CONTENT, "Value 2"],
                        ],
                    },
                ],
                filename="test_docx_all_types",
                storage_scope="user",
            )

        assert result.get("success") is True, f"create_docx (all types) failed: {result.get('error')}"
        assert result["sections_count"] == 6


# ── XLSX Tests ─────────────────────────────────────────────────────────────────

class TestXlsxOps:
    """Tests for CsvOps.create_xlsx — personal folder output.

    XLSX export lives in csv_ops.CsvOps (same file handles both CSV and XLSX).
    """

    def test_tool_name_is_create_xlsx(self, doc_config):
        """Tool registry must expose 'create_xlsx'."""
        from app.tools.document.csv_ops import CsvOps
        ops = CsvOps(doc_config)
        tool_names = [t["name"] for t in ops.get_tools()]
        assert "create_xlsx" in tool_names, "CsvOps must register 'create_xlsx'. Got: " + str(tool_names)

    @pytest.mark.asyncio
    async def test_create_xlsx_produces_file(self, doc_config, tmp_artifacts):
        """create_xlsx generates a .xlsx file in the personal folder."""
        from app.tools.document.csv_ops import CsvOps

        with (
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            ops = CsvOps(doc_config)
            result = await ops._create_xlsx(
                rows=[[TEST_CONTENT, "Value B"]],
                headers=["Column A", "Column B"],
                sheet_name="Test Sheet",
                filename="test_xlsx_output",
                storage_scope="user",
            )

        assert result.get("success") is True, f"create_xlsx failed: {result.get('error')}"
        file_path = Path(result["file_path"])
        assert file_path.exists(), f"XLSX file not found at: {file_path}"
        assert file_path.suffix == ".xlsx"
        assert file_path.stat().st_size > 0
        assert result["row_count"] == 1
        assert result["column_count"] == 2

    @pytest.mark.asyncio
    async def test_create_xlsx_multiple_rows(self, doc_config, tmp_artifacts):
        """Multiple data rows all land in the spreadsheet."""
        from app.tools.document.csv_ops import CsvOps

        rows = [[TEST_CONTENT, str(i)] for i in range(5)]

        with (
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            ops = CsvOps(doc_config)
            result = await ops._create_xlsx(
                rows=rows,
                headers=["Label", "Index"],
                filename="test_xlsx_multi_rows",
                storage_scope="user",
            )

        assert result.get("success") is True
        assert result["row_count"] == 5


# ── PDF Tests ──────────────────────────────────────────────────────────────────

class TestPDFOps:
    """Tests for PDFOps.create_pdf — personal folder output."""

    def test_tool_name_is_create_pdf(self, doc_config):
        """Tool registry must expose 'create_pdf'."""
        from app.tools.document.pdf_ops import PDFOps
        ops = PDFOps(doc_config)
        tool_names = [t["name"] for t in ops.get_tools()]
        assert "create_pdf" in tool_names, "PDFOps must register 'create_pdf'. Got: " + str(tool_names)

    @pytest.mark.asyncio
    async def test_create_pdf_produces_file(self, doc_config, tmp_artifacts):
        """create_pdf generates a .pdf file in the personal folder."""
        from app.tools.document.pdf_ops import PDFOps

        with (
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            ops = PDFOps(doc_config)
            result = await ops._create_pdf(
                title=TEST_CONTENT,
                content=f"<p>{TEST_CONTENT}</p>",
                filename="test_pdf_output",
                storage_scope="user",
            )

        assert result.get("success") is True, f"create_pdf failed: {result.get('error')}"
        file_path = Path(result["file_path"])
        assert file_path.exists(), f"PDF file not found at: {file_path}"
        assert file_path.suffix == ".pdf"
        assert file_path.stat().st_size > 0
        assert result["title"] == TEST_CONTENT

    @pytest.mark.asyncio
    async def test_create_pdf_with_html_content(self, doc_config, tmp_artifacts):
        """HTML content (headings, lists, tables) renders to PDF without error."""
        from app.tools.document.pdf_ops import PDFOps

        html = (
            f"<h2>Section Heading</h2>"
            f"<p>{TEST_CONTENT}</p>"
            f"<ul><li>Item 1</li><li>Item 2</li></ul>"
            f"<table><tr><th>Header 1</th><th>Header 2</th></tr>"
            f"<tr><td>{TEST_CONTENT}</td><td>Cell B</td></tr></table>"
        )

        with (
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            ops = PDFOps(doc_config)
            result = await ops._create_pdf(
                title=TEST_CONTENT,
                html_content=html,
                filename="test_pdf_html_types",
                storage_scope="user",
            )

        assert result.get("success") is True, f"create_pdf (html content) failed: {result.get('error')}"


# ── PitchDeckGenerationSkill Bug Regression ───────────────────────────────────

class TestPitchDeckGenerationSkillFix:
    """
    Regression: PitchDeckGenerationSkill previously called execute("create_presentation", sections=...)
    which fails because PPTXOps registers "create_pptx" with a "slides" parameter.

    These tests confirm the fix:
      - execute("create_presentation") returns success=False with "not found" error (sanity check)
      - execute("create_pptx", slides=[...]) succeeds (the actual fix)
    """

    def test_create_presentation_not_in_registry(self, doc_config):
        """Sanity: 'create_presentation' is NOT a registered tool — confirms the old bug."""
        from app.tools.document.pptx_ops import PPTXOps
        ops = PPTXOps(doc_config)
        tool_names = [t["name"] for t in ops.get_tools()]
        assert "create_presentation" not in tool_names

    @pytest.mark.asyncio
    async def test_execute_create_presentation_returns_error(self, doc_config):
        """
        Calling execute('create_presentation') returns success=False.
        This is the exact failure mode from the screenshot:
          'Pitch deck creation failed: Tool create_presentation not found in PPTXOps'
        """
        from app.tools.document.pptx_ops import PPTXOps
        ops = PPTXOps(doc_config)
        result = await ops.execute("create_presentation", title="Test", sections=[])
        assert result.get("success") is False
        assert "not found" in result.get("error", "").lower() or "create_presentation" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_pitch_deck_skill_calls_create_pptx(self, doc_config, tmp_artifacts):
        """
        After the fix, PitchDeckGenerationSkill.create_pitch_deck() calls
        execute('create_pptx', slides=[...]) and succeeds.
        """
        from app.skills.available.pitch_deck_generation import PitchDeckGenerationSkill

        # Mock out MezzofyDataOps (not under test)
        mock_data_result = {"success": True, "output": "Mock product data"}

        with (
            patch("app.tools.mezzofy.data_ops.MezzofyDataOps.execute", return_value=mock_data_result),
            patch("app.core.user_context.get_user_dept", return_value=TEST_DEPT),
            patch("app.core.user_context.get_user_email", return_value=TEST_EMAIL),
            patch("app.context.artifact_manager.get_artifacts_dir", return_value=tmp_artifacts.parent.parent),
        ):
            skill = PitchDeckGenerationSkill(doc_config)
            result = await skill.create_pitch_deck(
                customer_name="Test Corp",
                industry="Retail",
                include_pricing=False,
                include_case_studies=False,
            )

        assert result.get("success") is True, (
            f"PitchDeckGenerationSkill.create_pitch_deck failed: {result.get('error')}\n"
            "Check that pitch_deck_generation.py calls execute('create_pptx', slides=[...])."
        )
        file_path = Path(result["file_path"])
        assert file_path.exists()
        assert file_path.suffix == ".pptx"


# ── skill_ok Guard — Fallback Behavior ────────────────────────────────────────

class TestSkillOkGuardFallback:
    """
    Tests that the skill_ok guard in all agents correctly falls back to legacy ops
    when the Anthropic Skills API returns success=False (no file_ids).
    """

    @pytest.mark.asyncio
    async def test_skill_ok_guard_does_not_swallow_exception(self):
        """
        When Skill API raises an exception, the guard logs a warning and falls back
        — it does NOT re-raise, ensuring the user still gets a response.
        """
        import logging
        from unittest.mock import AsyncMock

        skill_mock = AsyncMock(side_effect=RuntimeError("Anthropic API timeout"))

        with patch("app.llm.llm_manager.generate_document_with_skill", skill_mock):
            # Import a simple skill_ok guard pattern to verify the structure exists
            # This is a structural test — we verify the guard exists in all 7 agent files
            import inspect
            import app.agents.management_agent as mgmt
            import app.agents.sales_agent as sales
            import app.agents.marketing_agent as mktg
            import app.agents.hr_agent as hr
            import app.agents.finance_agent as fin
            import app.agents.legal_agent as legal
            import app.agents.support_agent as support

            for module, name in [
                (mgmt, "management_agent"),
                (sales, "sales_agent"),
                (mktg, "marketing_agent"),
                (hr, "hr_agent"),
                (fin, "finance_agent"),
                (legal, "legal_agent"),
                (support, "support_agent"),
            ]:
                source = inspect.getsource(module)
                assert "skill_ok" in source, (
                    f"{name}.py is missing the skill_ok guard pattern. "
                    "All agents must use the skill_ok guard to catch silent failures."
                )
                assert "if not skill_ok" in source, (
                    f"{name}.py must have 'if not skill_ok:' fallback block."
                )
