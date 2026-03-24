"""
Unit tests: AnthropicClient timeout configuration.
Ensures the Anthropic client uses a granular httpx.Timeout with a sufficient
read timeout for long-running research tool-use chains (>60s per LLM call).
"""
import inspect
import pytest

pytestmark = pytest.mark.unit


def test_anthropic_client_does_not_use_flat_60s_timeout():
    """
    The flat timeout=60.0 must be removed.
    Research tasks need >60s per LLM call — a flat 60s timeout causes infinite retry loops.
    """
    from app.llm.anthropic_client import AnthropicClient
    source = inspect.getsource(AnthropicClient.__init__)
    assert "timeout=60.0" not in source, (
        "AnthropicClient still uses flat timeout=60.0. "
        "This causes LLM calls to time out on research tasks. "
        "Replace with httpx.Timeout(connect=10, read=600, write=30, pool=10)."
    )


def test_anthropic_client_uses_sufficient_read_timeout():
    """
    The read timeout must be >= 300s to support long research tool-use chains.
    """
    from app.llm.anthropic_client import AnthropicClient
    source = inspect.getsource(AnthropicClient.__init__)
    # Accept any read= value >= 300
    import re
    match = re.search(r'read\s*=\s*(\d+(?:\.\d+)?)', source)
    assert match, (
        "AnthropicClient.__init__ does not set a 'read=' timeout in httpx.Timeout. "
        "Must use httpx.Timeout(read=600.0, ...) for research task support."
    )
    read_timeout = float(match.group(1))
    assert read_timeout >= 300, (
        f"AnthropicClient read timeout is {read_timeout}s — must be >= 300s "
        f"for long-running research LLM calls."
    )


def test_process_delegated_agent_task_has_soft_time_limit():
    """
    process_delegated_agent_task must declare soft_time_limit to prevent runaway tasks.
    """
    import inspect
    from app.tasks import tasks as tasks_module
    source = inspect.getsource(tasks_module)
    assert "soft_time_limit" in source, (
        "process_delegated_agent_task is missing soft_time_limit. "
        "Without it, a stuck agent task will loop forever and block the Celery worker."
    )
