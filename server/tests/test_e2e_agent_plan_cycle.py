"""
E2E integration test: Agent Plan full execution cycle via live EC2 API.

Validates the complete PLAN→DELEGATE→AGGREGATE pipeline:
  JWT auth → POST /chat/send (long-running keyword triggers Celery)
  → plan created in Redis DB3 → steps executed → COMPLETED status
  → final_output populated → each step has individual output

# ── HOW TO RUN ─────────────────────────────────────────────────────────────────
#
#   Run ON EC2 (or any host with access to 3.1.255.48:8000):
#
#   MZ_TEST_ADMIN_PASSWORD="<password>" \\
#   pytest tests/test_e2e_agent_plan_cycle.py -v -m integration 2>&1 | \\
#   tee tests/results/agent-plan-cycle-report.md
#
#   Optional env var overrides:
#     MZ_TEST_BASE_URL          — default: http://3.1.255.48:8000
#                                 (use http://localhost:8000 when running on EC2)
#     MZ_TEST_ADMIN_EMAIL       — default: admin@mezzofy.com
#     MZ_TEST_ADMIN_PASSWORD    — REQUIRED, no default
#     MZ_PLAN_POLL_TIMEOUT_S    — default: 300 (5 minutes)
#     MZ_PLAN_POLL_INTERVAL_S   — default: 10 (poll every 10 seconds)
#
#   Prerequisites:
#     - mezzofy-api.service running on target host
#     - mezzofy-celery.service running (executes plan steps)
#     - Redis accessible to both services
#     - MZ_TEST_ADMIN_PASSWORD env var set
#
# ──────────────────────────────────────────────────────────────────────────────

Requirements (all must be true to run):
  - Live mezzofy-api.service accessible at MZ_TEST_BASE_URL
  - Live mezzofy-celery.service consuming the "background" Celery queue
  - MZ_TEST_ADMIN_PASSWORD env var set (never hardcoded)
"""

import os
import time

import pytest
import requests

pytestmark = pytest.mark.integration

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = os.getenv("MZ_TEST_BASE_URL", "http://3.1.255.48:8000")
ADMIN_EMAIL = os.getenv("MZ_TEST_ADMIN_EMAIL", "admin@mezzofy.com")
ADMIN_PASSWORD = os.getenv("MZ_TEST_ADMIN_PASSWORD")  # REQUIRED — no default

POLL_TIMEOUT_S = int(os.getenv("MZ_PLAN_POLL_TIMEOUT_S", "300"))   # 5 minutes
POLL_INTERVAL_S = int(os.getenv("MZ_PLAN_POLL_INTERVAL_S", "10"))  # 10 seconds

# The goal message sent to /chat/send.
# "Research" is in _LONG_RUNNING_KEYWORDS in chat.py — this guarantees the
# server takes the async Celery path and returns 202. It also matches the
# _RESEARCH_KEYWORDS list so it is routed to the research queue.
GOAL_MESSAGE = "Research the Digital Coupon market for Singapore."
GOAL_KEYWORD = "Digital Coupon"   # used for plan detection in GET /api/plans list

# ── Module-level skip guard ───────────────────────────────────────────────────

if not ADMIN_PASSWORD:
    pytest.skip(
        "MZ_TEST_ADMIN_PASSWORD not set — cannot run E2E plan cycle tests without credentials",
        allow_module_level=True,
    )

# ── Shared result cache ───────────────────────────────────────────────────────
#
# All five test methods share a single run of the full plan cycle.
# We execute the cycle once here at module level (in a module-scoped fixture)
# and store the results in this dict. Each test reads from it.
#
# Structure populated by `plan_result` fixture:
#   {
#     "send_status_code": int,        # HTTP status from POST /chat/send
#     "send_body": dict,              # full response body from POST /chat/send
#     "task_id": str,                 # agent_tasks row id (from 202 body)
#     "session_id": str,              # resolved session_id (from 202 body)
#     "plan_id": str | None,          # found via GET /api/plans lookup
#     "final_plan": dict | None,      # full plan dict once COMPLETED/FAILED
#     "poll_elapsed_s": float,        # time spent polling
#     "poll_timed_out": bool,         # True if timeout reached before terminal state
#   }
#
_result_cache: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth_headers(token: str) -> dict:
    """Return Authorization header dict for a Bearer token."""
    return {"Authorization": f"Bearer {token}"}


def _login() -> str:
    """
    Two-step OTP login:
      Step 1: POST /auth/login → otp_required + otp_token
      Step 2: Read OTP code from Redis DB0 (key: login_otp:{otp_token})
              POST /auth/verify-otp → access_token

    Reading OTP from Redis avoids needing email access in E2E tests.
    Requires Redis to be accessible (works on EC2 running localhost).
    """
    import json as _json
    import redis as _redis

    # Step 1: Submit credentials → get otp_token
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert resp.status_code == 200, (
        f"Login step 1 failed (HTTP {resp.status_code}). "
        f"Check MZ_TEST_ADMIN_EMAIL / MZ_TEST_ADMIN_PASSWORD. "
        f"Response: {resp.text[:300]}"
    )
    body = resp.json()
    assert body.get("status") == "otp_required", (
        f"Unexpected login response (expected otp_required). Body: {body}"
    )
    otp_token = body.get("otp_token")
    assert otp_token, f"Login response missing otp_token. Body: {body}"

    # Step 2: Read OTP code directly from Redis DB0 (TTL=300s, key=login_otp:{otp_token})
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = _redis.from_url(redis_url, db=0, decode_responses=True)
    raw = r.get(f"login_otp:{otp_token}")
    assert raw, (
        f"OTP not found in Redis (key=login_otp:{otp_token}). "
        f"It may have expired (TTL=300s) or Redis DB is incorrect."
    )
    otp_code = _json.loads(raw)["code"]

    # Step 3: Verify OTP → get access_token
    verify_resp = requests.post(
        f"{BASE_URL}/auth/verify-otp",
        json={"otp_token": otp_token, "code": otp_code},
        timeout=30,
    )
    assert verify_resp.status_code == 200, (
        f"Login step 2 (verify-otp) failed (HTTP {verify_resp.status_code}). "
        f"Response: {verify_resp.text[:300]}"
    )
    token = verify_resp.json().get("access_token")
    assert token, f"verify-otp response missing access_token. Body: {verify_resp.json()}"
    return token


def _find_plan_by_goal(token: str, keyword: str, retries: int = 3, wait_s: int = 5) -> str | None:
    """
    GET /api/plans (list) and find a plan whose goal contains `keyword`.

    Retries up to `retries` times with `wait_s` seconds between attempts to
    account for the brief delay between POST /chat/send and PlanManager.create_plan().

    Returns the plan_id string if found, None otherwise.
    """
    headers = _auth_headers(token)
    for attempt in range(retries):
        try:
            resp = requests.get(
                f"{BASE_URL}/api/plans",
                params={"limit": 10},
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            if attempt < retries - 1:
                time.sleep(wait_s)
                continue
            raise

        if resp.status_code != 200:
            if attempt < retries - 1:
                time.sleep(wait_s)
                continue
            return None

        plans = resp.json().get("plans", [])
        for p in plans:
            goal = p.get("goal", "")
            if keyword.lower() in goal.lower():
                return p["plan_id"]

        if attempt < retries - 1:
            # Plan may not be written to Redis yet — wait and retry
            time.sleep(wait_s)

    return None


def _poll_plan_until_terminal(token: str, plan_id: str) -> tuple[dict, float, bool]:
    """
    Poll GET /api/plans/{plan_id} every POLL_INTERVAL_S seconds until the plan
    reaches a terminal status (COMPLETED or FAILED) or POLL_TIMEOUT_S is reached.

    Returns:
        (final_plan_dict, elapsed_seconds, timed_out)

    terminal statuses: COMPLETED, FAILED (per ExecutionPlan dataclass)
    """
    headers = _auth_headers(token)
    terminal_statuses = {"COMPLETED", "FAILED"}
    start = time.monotonic()
    max_iterations = POLL_TIMEOUT_S // POLL_INTERVAL_S
    final_plan: dict = {}

    for iteration in range(max_iterations + 1):
        try:
            resp = requests.get(
                f"{BASE_URL}/api/plans/{plan_id}",
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            # Network hiccup — keep polling
            time.sleep(POLL_INTERVAL_S)
            continue

        if resp.status_code == 200:
            final_plan = resp.json()
            plan_status = final_plan.get("status", "")
            if plan_status in terminal_statuses:
                elapsed = time.monotonic() - start
                return final_plan, elapsed, False

        # Not terminal yet — wait before next poll
        elapsed_so_far = time.monotonic() - start
        if elapsed_so_far >= POLL_TIMEOUT_S:
            break
        time.sleep(POLL_INTERVAL_S)

    elapsed = time.monotonic() - start
    return final_plan, elapsed, True


# ── Module-scoped fixture — runs the full cycle once ─────────────────────────

@pytest.fixture(scope="module")
def plan_result() -> dict:
    """
    Execute the full plan cycle exactly once and cache the result.

    All tests in this module share this fixture. The cycle:
      1. Login → JWT token
      2. POST /chat/send with GOAL_MESSAGE → 202 queued
      3. Find plan_id via GET /api/plans (with retries for creation delay)
      4. Poll GET /api/plans/{plan_id} until COMPLETED/FAILED or timeout

    Returns the _result_cache dict populated with all intermediate and final values.
    """
    if _result_cache:
        # Already populated — return immediately (pytest module scope ensures
        # this only runs once, but guard against any edge case)
        return _result_cache

    # Step 1: Authenticate
    token = _login()

    # Step 2: Send goal message — this triggers Celery + PlanManager
    send_resp = requests.post(
        f"{BASE_URL}/chat/send",
        json={
            "message": GOAL_MESSAGE,
            # No session_id — let the server create a new session
        },
        headers=_auth_headers(token),
        timeout=60,
    )

    _result_cache["send_status_code"] = send_resp.status_code
    _result_cache["send_body"] = {}
    _result_cache["task_id"] = None
    _result_cache["session_id"] = None
    _result_cache["plan_id"] = None
    _result_cache["final_plan"] = None
    _result_cache["poll_elapsed_s"] = 0.0
    _result_cache["poll_timed_out"] = False

    if send_resp.status_code not in (200, 202):
        # Cannot proceed — tests will fail with clear messages below
        return _result_cache

    body = send_resp.json()
    _result_cache["send_body"] = body

    # Extract task_id and session_id from 202 response body
    # chat.py returns: {"status": "queued", "task_id": ..., "session_id": ...}
    _result_cache["task_id"] = body.get("task_id")
    _result_cache["session_id"] = body.get("session_id")

    # Step 3: Find the plan in /api/plans list
    # PlanManager.create_plan() is called async from the Celery task — there is
    # a short window (typically < 5s) between the 202 response and the plan
    # appearing in Redis. _find_plan_by_goal retries 3x with 5s waits.
    plan_id = _find_plan_by_goal(token, GOAL_KEYWORD)
    _result_cache["plan_id"] = plan_id

    if not plan_id:
        # Cannot poll — tests will fail with clear messages
        return _result_cache

    # Step 4: Poll until terminal status
    final_plan, elapsed, timed_out = _poll_plan_until_terminal(token, plan_id)
    _result_cache["final_plan"] = final_plan
    _result_cache["poll_elapsed_s"] = elapsed
    _result_cache["poll_timed_out"] = timed_out

    return _result_cache


# ── Test class ────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestAgentPlanFullCycle:
    """
    End-to-end tests for the full Agent Plan execution cycle.

    All tests call the live server at MZ_TEST_BASE_URL (default: http://3.1.255.48:8000).
    No mocks — real Celery, real Redis, real LLM (Claude), real plan execution.

    All tests share a single `plan_result` fixture execution to avoid triggering
    multiple plans for the same goal (which would waste LLM tokens and EC2 time).
    """

    def test_plan_created_from_chat_message(self, plan_result: dict) -> None:
        """
        POST /chat/send with a long-running keyword returns 202 (queued),
        and a plan appears in GET /api/plans within the polling window.

        Validates:
          - /chat/send accepted the message (202 or 200)
          - Response contains task_id and session_id (async path)
          - A plan matching the goal keyword is discoverable via GET /api/plans
        """
        send_status = plan_result["send_status_code"]
        assert send_status in (200, 202), (
            f"POST /chat/send returned HTTP {send_status} (expected 202 for long-running task). "
            f"The message '{GOAL_MESSAGE}' contains 'research' which should trigger the async Celery path. "
            f"Body: {plan_result['send_body']}"
        )

        body = plan_result["send_body"]

        # For the async (202) path, the body must include task_id and session_id
        if send_status == 202:
            assert body.get("task_id"), (
                f"202 response missing task_id. "
                f"chat.py inserts an agent_tasks row and returns task_id. "
                f"Body: {body}"
            )
            assert body.get("session_id"), (
                f"202 response missing session_id. "
                f"chat.py resolves/creates the session before queuing. "
                f"Body: {body}"
            )

        plan_id = plan_result["plan_id"]
        assert plan_id is not None, (
            f"No plan found in GET /api/plans matching goal keyword '{GOAL_KEYWORD}'. "
            f"Checked up to 3 times with 5s intervals after POST /chat/send. "
            f"Possible causes: "
            f"(1) mezzofy-celery.service is not running; "
            f"(2) PlanManager.create_plan() failed (check server logs); "
            f"(3) AgentRegistry is empty (run scripts/migrate.py on EC2). "
            f"task_id={plan_result['task_id']} session_id={plan_result['session_id']}"
        )

    def test_plan_steps_progress_to_completion(self, plan_result: dict) -> None:
        """
        The plan transitions from PENDING/IN_PROGRESS to COMPLETED (not FAILED)
        within the polling timeout.

        Validates:
          - plan_id was found (prerequisite — skip with informative message if not)
          - Polling did not time out
          - Final plan status is COMPLETED (not FAILED, PENDING, IN_PROGRESS)
        """
        plan_id = plan_result["plan_id"]
        if plan_id is None:
            pytest.skip(
                "plan_id not found — test_plan_created_from_chat_message must pass first"
            )

        assert not plan_result["poll_timed_out"], (
            f"Plan did not reach a terminal status within {POLL_TIMEOUT_S}s. "
            f"Last known status: {plan_result['final_plan'].get('status', 'unknown')}. "
            f"Elapsed: {plan_result['poll_elapsed_s']:.1f}s. "
            f"plan_id={plan_id}. "
            f"Check mezzofy-celery.service logs on EC2 for errors."
        )

        final_plan = plan_result["final_plan"]
        assert final_plan, (
            f"final_plan is empty despite poll completing. plan_id={plan_id}"
        )

        status = final_plan.get("status")
        assert status == "COMPLETED", (
            f"Plan ended with status={status!r} (expected 'COMPLETED'). "
            f"plan_id={plan_id}. "
            f"Steps summary: "
            + ", ".join(
                f"{s.get('step_id')}:{s.get('status')}"
                for s in final_plan.get("steps", [])
            )
            + f". Check plan detail: GET /api/plans/{plan_id}"
        )

    def test_plan_final_output_is_populated(self, plan_result: dict) -> None:
        """
        The plan's final_output field is not None and contains meaningful content.

        Validates:
          - final_output is set (not None, not empty string)
          - final_output has at least 50 characters (meaningful synthesis)

        Note: final_output is set by the orchestrator's AGGREGATE phase which
        synthesises all step outputs into a single response.
        """
        plan_id = plan_result["plan_id"]
        if plan_id is None:
            pytest.skip("plan_id not found — test_plan_created_from_chat_message must pass first")

        final_plan = plan_result["final_plan"]
        if not final_plan:
            pytest.skip("final_plan not populated — test_plan_steps_progress_to_completion must pass first")

        if final_plan.get("status") == "FAILED":
            pytest.skip(
                f"Plan FAILED — skipping output assertion. "
                f"plan_id={plan_id}. Run test_plan_steps_progress_to_completion to diagnose."
            )

        final_output = final_plan.get("final_output")
        assert final_output is not None, (
            f"plan.final_output is None for a COMPLETED plan. "
            f"plan_id={plan_id}. "
            f"The orchestrator's synthesis step should populate this field. "
            f"Check orchestrator_tasks.py or management_agent.py AGGREGATE phase."
        )

        assert isinstance(final_output, str) and len(final_output) >= 50, (
            f"plan.final_output is too short ({len(final_output) if isinstance(final_output, str) else type(final_output).__name__} chars). "
            f"Expected a meaningful synthesis of at least 50 characters. "
            f"Got: {str(final_output)[:200]!r}"
        )

    def test_plan_steps_have_individual_outputs(self, plan_result: dict) -> None:
        """
        Every COMPLETED step in the plan has a non-null output field.

        Validates:
          - Each step with status=COMPLETED has step.output set (not None)
          - step.output is a non-empty dict

        Note: step.output is set by orchestrator_tasks.py after each agent
        executes the step and returns a result.
        """
        plan_id = plan_result["plan_id"]
        if plan_id is None:
            pytest.skip("plan_id not found — test_plan_created_from_chat_message must pass first")

        final_plan = plan_result["final_plan"]
        if not final_plan:
            pytest.skip("final_plan not populated — test_plan_steps_progress_to_completion must pass first")

        steps = final_plan.get("steps", [])
        assert steps, (
            f"Plan has no steps. plan_id={plan_id}. "
            f"PlanManager.create_plan() should produce at least 1 step."
        )

        completed_steps = [s for s in steps if s.get("status") == "COMPLETED"]
        assert completed_steps, (
            f"No steps have status=COMPLETED. All steps: "
            + ", ".join(f"{s.get('step_id')}:{s.get('status')}" for s in steps)
            + f". plan_id={plan_id}"
        )

        for step in completed_steps:
            step_id = step.get("step_id", "unknown")
            output = step.get("output")
            assert output is not None, (
                f"Step {step_id!r} has status=COMPLETED but output is None. "
                f"The orchestrator must set step.output after execution. "
                f"plan_id={plan_id}"
            )
            assert isinstance(output, dict), (
                f"Step {step_id!r} output should be a dict, got {type(output).__name__}. "
                f"plan_id={plan_id}"
            )
            # output dict should have at least one key with content
            assert output, (
                f"Step {step_id!r} output is an empty dict. "
                f"Expected at least one key (e.g. 'summary', 'result', 'content'). "
                f"plan_id={plan_id}"
            )

    def test_plan_completes_within_timeout(self, plan_result: dict) -> None:
        """
        The full plan cycle (from POST /chat/send to COMPLETED status) finishes
        within the configured timeout (MZ_PLAN_POLL_TIMEOUT_S, default 300s).

        This test also verifies the overall pipeline timing is acceptable for
        a research task: ideally under 3 minutes, hard limit 5 minutes.

        Validates:
          - poll_timed_out is False
          - poll_elapsed_s < POLL_TIMEOUT_S
          - (Soft warning) poll_elapsed_s < 180s (3 minutes is a reasonable target)
        """
        plan_id = plan_result["plan_id"]
        if plan_id is None:
            pytest.skip("plan_id not found — test_plan_created_from_chat_message must pass first")

        assert not plan_result["poll_timed_out"], (
            f"Plan execution exceeded the {POLL_TIMEOUT_S}s hard timeout. "
            f"Elapsed: {plan_result['poll_elapsed_s']:.1f}s. "
            f"plan_id={plan_id}. "
            f"Either increase MZ_PLAN_POLL_TIMEOUT_S or investigate slow step execution."
        )

        elapsed = plan_result["poll_elapsed_s"]
        assert elapsed < POLL_TIMEOUT_S, (
            f"Elapsed time {elapsed:.1f}s exceeds configured timeout {POLL_TIMEOUT_S}s. "
            f"plan_id={plan_id}"
        )

        # Soft performance target: research plan should complete within 3 minutes.
        # This is a warning assertion — if it fails, the plan is slow but not broken.
        soft_target_s = 180
        if elapsed > soft_target_s:
            # Print a warning but do not fail the test — timing varies by LLM load
            print(
                f"\nPERFORMANCE WARNING: plan completed in {elapsed:.1f}s "
                f"(soft target: {soft_target_s}s). "
                f"Consider tuning Celery worker concurrency or agent step count. "
                f"plan_id={plan_id}"
            )

        # Final confirmation: status must be COMPLETED (not FAILED)
        final_status = plan_result.get("final_plan", {}).get("status", "unknown")
        assert final_status == "COMPLETED", (
            f"Plan completed within timeout ({elapsed:.1f}s) but with status={final_status!r}. "
            f"plan_id={plan_id}"
        )
