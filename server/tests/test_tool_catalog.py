"""
Tool catalog: list every tool available to Claude Sonnet 4.6 and Kimi K2.5.

Both models receive IDENTICAL tool lists — no per-model filtering exists.
Filtering only happens when a calling agent passes an explicit `tool_names` subset.

This test requires NO API keys and NO running server.
It instantiates ToolExecutor directly and dumps all registered tool definitions.

Run:
    pytest tests/test_tool_catalog.py -v -s --no-cov

    # Or as a plain Python script (no pytest):
    python tests/test_tool_catalog.py

Output:
    tests/results/tool_catalog_YYYYMMDD.md
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

RESULTS_DIR = Path(__file__).parent / "results"
REPORT_FILE = RESULTS_DIR / f"tool_catalog_{datetime.now().strftime('%Y%m%d')}.md"

# ── Category prefix map ───────────────────────────────────────────────────────

_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (
        ("outlook_", "teams_", "send_push", "personal_", "check_ms365"),
        "Communication",
    ),
    (
        (
            "create_pdf", "read_pdf", "merge_pdf",
            "create_pptx", "read_pptx",
            "create_docx", "read_docx",
            "create_csv", "create_xlsx", "read_csv",
            "create_txt", "read_txt",
        ),
        "Document",
    ),
    (
        (
            "ocr_image", "analyze_image", "resize_image", "extract_exif",
            "extract_key_frames", "extract_audio_track", "get_video_info", "analyze_video",
            "transcribe_audio", "detect_language", "convert_audio", "get_audio_info",
        ),
        "Media",
    ),
    (
        ("open_page", "screenshot_page", "extract_text", "scrape_", "linkedin_", "li_at"),
        "Web",
    ),
    (
        (
            "query_", "create_lead", "update_lead", "search_leads", "get_lead",
            "export_leads", "get_pipeline", "get_stale_leads",
            "get_employee", "list_employees", "create_employee", "update_employee",
            "set_employee_status", "get_employee_profile",
            "apply_leave", "get_leave_", "update_leave_", "get_pending_",
            "get_leave_summary",
        ),
        "Database / CRM / HR",
    ),
    (
        (
            "get_products", "get_case_studies", "get_pricing", "get_feature_specs",
            "semantic_search", "search_knowledge", "get_template",
            "get_brand_guidelines", "get_playbook",
        ),
        "Mezzofy KB",
    ),
    (
        ("create_scheduled_job", "list_scheduled_jobs", "delete_scheduled_job",
         "run_job_now", "search_user_files"),
        "Scheduler / Files",
    ),
]


def _categorize(tool_name: str) -> str:
    for prefixes, category in _CATEGORY_RULES:
        if any(tool_name.startswith(p) or tool_name == p.rstrip("_") for p in prefixes):
            return category
    return "Other"


def _truncate(text: str, max_len: int = 80) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


# ── Main catalog generation ───────────────────────────────────────────────────

def generate_catalog() -> str:
    """Instantiate ToolExecutor, fetch all definitions, return formatted Markdown."""
    # ToolExecutor auto-loads config.yaml (or example) — no API keys needed
    from app.tools.tool_executor import ToolExecutor

    executor = ToolExecutor()
    tools: list[dict] = executor.get_all_definitions()

    # Sort by category then tool name
    tools_sorted = sorted(tools, key=lambda t: (_categorize(t["name"]), t["name"]))

    # Count by category
    category_counts: dict[str, int] = {}
    for t in tools_sorted:
        cat = _categorize(t["name"])
        category_counts[cat] = category_counts.get(cat, 0) + 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = [
        "# Tool Catalog — Claude Sonnet 4.6 & Kimi K2.5",
        f"**Generated:** {now}",
        "",
        "> Both models receive **identical** tool sets.",
        "> Filtering only occurs when a calling agent passes an explicit `tool_names` subset.",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total tools | {len(tools)} |",
        f"| Categories | {len(category_counts)} |",
    ]
    for cat, count in sorted(category_counts.items()):
        lines.append(f"| {cat} | {count} tools |")

    lines += [
        "",
        "---",
        "",
        "## Full Tool List",
        "",
        "| # | Category | Tool Name | Description | Required Params |",
        "|---|----------|-----------|-------------|-----------------|",
    ]

    for i, tool in enumerate(tools_sorted, start=1):
        name = tool.get("name", "")
        desc = _truncate(tool.get("description", ""), 80)
        params = tool.get("parameters", {})
        required = ", ".join(params.get("required", [])) or "—"
        cat = _categorize(name)
        lines.append(f"| {i} | {cat} | `{name}` | {desc} | {required} |")

    lines += ["", "---", ""]
    return "\n".join(lines)


def write_catalog() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    content = generate_catalog()
    REPORT_FILE.write_text(content, encoding="utf-8")
    return REPORT_FILE


# ── Pytest test ───────────────────────────────────────────────────────────────

class TestToolCatalog:

    def test_generate_tool_catalog(self):
        """
        Generates and saves the complete tool catalog for both LLMs.
        No API keys or running server required.
        """
        report_path = write_catalog()

        # Basic sanity assertions
        content = report_path.read_text(encoding="utf-8")
        assert "Tool Catalog" in content
        assert "claude-sonnet" in content.lower() or "Claude Sonnet" in content
        # At least 50 tools expected
        tool_lines = [l for l in content.splitlines() if l.startswith("| ") and "`" in l]
        assert len(tool_lines) >= 50, f"Expected ≥50 tools, found {len(tool_lines)}"

        print(f"\n[Catalog] {len(tool_lines)} tools written to: {report_path}")
        print(f"[Catalog] Run:  cat {report_path}  (or scp to local)")


# ── Standalone entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Allow running directly: python tests/test_tool_catalog.py
    sys.path.insert(0, str(Path(__file__).parent.parent))
    path = write_catalog()
    print(f"Tool catalog written to: {path}")
    # Print a preview (first 40 lines)
    lines = path.read_text(encoding="utf-8").splitlines()
    print("\n".join(lines[:40]))
    if len(lines) > 40:
        print(f"... ({len(lines) - 40} more lines in file)")
