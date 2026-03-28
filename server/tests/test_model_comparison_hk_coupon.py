"""
Integration tests: Claude Sonnet 4.6 vs Kimi K2.5 — HK coupon market research.

Sends the identical prompt to both models and saves a Markdown comparison
report with full responses + token usage for manual review.

Requirements:
  - ANTHROPIC_API_KEY env var for Claude test
  - KIMI_API_KEY env var for Kimi test (each test skips independently if key absent)

Run both (with live output):
  cd server
  ANTHROPIC_API_KEY=<key> KIMI_API_KEY=<key> \\
    pytest tests/test_model_comparison_hk_coupon.py -v -m integration -s --no-cov

Run one model only:
  pytest tests/test_model_comparison_hk_coupon.py::TestHKCouponResearch::test_claude_sonnet_hk_coupon_research -v -m integration -s --no-cov
  pytest tests/test_model_comparison_hk_coupon.py::TestHKCouponResearch::test_kimi_k2_hk_coupon_research -v -m integration -s --no-cov

Output report:
  tests/results/model_comparison_hk_coupon_YYYYMMDD.md
"""

import os
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

PROMPT = "research hong kong digital coupon market 2026 trend"

RESULTS_DIR = Path(__file__).parent / "results"
REPORT_FILE = RESULTS_DIR / f"model_comparison_hk_coupon_{datetime.now().strftime('%Y%m%d')}.md"


def _ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_report_header() -> None:
    """Write the report header only once (when file does not yet exist)."""
    if REPORT_FILE.exists():
        return
    _ensure_results_dir()
    header = (
        f"# Model Comparison: HK Digital Coupon Market Research\n"
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"## Prompt\n\n"
        f"> {PROMPT}\n\n"
        f"---\n\n"
    )
    REPORT_FILE.write_text(header, encoding="utf-8")


def _append_result(section_title: str, model_id: str, content: str,
                   input_tokens: int, output_tokens: int, stop_reason: str) -> None:
    """Append a model result section to the comparison report."""
    total = input_tokens + output_tokens
    section = (
        f"## {section_title}\n\n"
        f"**Model:** `{model_id}`  \n"
        f"**Tokens:** input={input_tokens}  output={output_tokens}  total={total}  \n"
        f"**Stop reason:** `{stop_reason}`\n\n"
        f"### Response\n\n"
        f"{content}\n\n"
        f"---\n\n"
    )
    with REPORT_FILE.open("a", encoding="utf-8") as f:
        f.write(section)


def _print_result(label: str, model_id: str, content: str,
                  input_tokens: int, output_tokens: int, stop_reason: str) -> None:
    total = input_tokens + output_tokens
    separator = "=" * 72
    print(f"\n{separator}")
    print(f"  {label}")
    print(f"  Model      : {model_id}")
    print(f"  Tokens     : input={input_tokens}  output={output_tokens}  total={total}")
    print(f"  Stop reason: {stop_reason}")
    print(separator)
    print(content)
    print(separator)


class TestHKCouponResearch:

    # ── Claude Sonnet 4.6 ──────────────────────────────────────────────────────

    async def test_claude_sonnet_hk_coupon_research(self):
        """
        Calls Claude Sonnet 4.6 with the HK coupon market research prompt.
        Asserts a substantive response is returned and token usage is non-zero.
        Saves full response + token counts to the comparison report.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set — skipping Claude test")

        from app.llm.anthropic_client import AnthropicClient

        config = {
            "llm": {
                "claude": {
                    "model": "claude-sonnet-4-6",
                    "api_key": api_key,
                    "max_tokens": 4096,
                    "temperature": 0.7,
                }
            }
        }

        client = AnthropicClient(config)
        result = await client.chat(
            messages=[{"role": "user", "content": PROMPT}],
        )

        content = result.get("content", "")
        input_tokens = result.get("usage", {}).get("input_tokens", 0)
        output_tokens = result.get("usage", {}).get("output_tokens", 0)
        stop_reason = result.get("stop_reason", "unknown")
        model_id = result.get("model", "claude-sonnet-4-6")

        # Assertions
        assert content, "Claude returned an empty response"
        assert len(content) > 100, f"Response suspiciously short ({len(content)} chars)"
        assert input_tokens > 0, "Claude reported 0 input tokens — usage tracking broken"
        assert output_tokens > 0, "Claude reported 0 output tokens — usage tracking broken"

        # Print to terminal (visible with pytest -s)
        _print_result(
            label="CLAUDE SONNET 4.6",
            model_id=model_id,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
        )

        # Save to report
        _write_report_header()
        _append_result(
            section_title="Claude Sonnet 4.6",
            model_id=model_id,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
        )
        print(f"\n[Report] Saved to: {REPORT_FILE}")

    # ── Kimi K2.5 ─────────────────────────────────────────────────────────────

    async def test_kimi_k2_hk_coupon_research(self):
        """
        Calls Kimi K2.5 with the HK coupon market research prompt.
        Uses a direct non-streaming call to obtain real token usage counts
        (KimiClient.chat() streams internally and returns usage=0 for text-only
        requests — this test bypasses that limitation without modifying production
        code).
        Saves full response + token counts to the comparison report.
        """
        api_key = os.getenv("KIMI_API_KEY", "")
        if not api_key:
            pytest.skip("KIMI_API_KEY not set — skipping Kimi test")

        from app.llm.kimi_client import KimiClient

        config = {
            "llm": {
                "kimi": {
                    "model": "kimi-k2.5",
                    "api_key": api_key,
                    "base_url": "https://api.moonshot.ai/v1",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                }
            }
        }

        kimi = KimiClient(config)

        # Call the underlying OpenAI-compatible client directly (non-streaming)
        # so that `response.usage` contains real token counts.
        messages = [{"role": "user", "content": PROMPT}]
        response = await kimi._client.chat.completions.create(
            model=kimi._model,
            max_tokens=kimi._max_tokens,
            temperature=1,  # kimi-k2.5 only accepts temperature=1
            messages=messages,
            stream=False,
        )

        choice = response.choices[0] if response.choices else None
        assert choice is not None, "Kimi returned no choices"

        content = choice.message.content or ""
        stop_reason = choice.finish_reason or "stop"
        model_id = response.model or kimi._model

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        # Assertions
        assert content, "Kimi returned an empty response"
        assert len(content) > 100, f"Response suspiciously short ({len(content)} chars)"
        assert input_tokens > 0, "Kimi reported 0 input tokens — check API response"
        assert output_tokens > 0, "Kimi reported 0 output tokens — check API response"

        # Print to terminal (visible with pytest -s)
        _print_result(
            label="KIMI K2.5",
            model_id=model_id,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
        )

        # Save to report
        _write_report_header()
        _append_result(
            section_title="Kimi K2.5",
            model_id=model_id,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
        )
        print(f"\n[Report] Saved to: {REPORT_FILE}")
