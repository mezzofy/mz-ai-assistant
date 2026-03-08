"""
Integration test: Research task end-to-end validation.

Sends a real research request to the live server, polls until the Celery
worker completes it, then validates the task is `completed` and the result
includes a downloadable .txt artifact.

Requirements:
  - Server running at TEST_SERVER_URL (default: http://localhost:8000)
  - Celery worker active and connected to the same broker
  - Anthropic API key configured on the server
  - TEST_JWT_TOKEN env var set (or uses make_token("finance_manager") with test secret)

Run:
  # Against EC2:
  TEST_SERVER_URL=http://3.1.255.48:8000 TEST_JWT_TOKEN=<jwt> \\
    pytest tests/test_integration_research_task.py -v -m integration --no-cov

  # Against local dev server:
  pytest tests/test_integration_research_task.py -v -m integration --no-cov
"""

import asyncio
import os

import httpx
import pytest

from tests.conftest import make_token

BASE_URL = os.getenv("TEST_SERVER_URL", "http://localhost:8000")
TOKEN = os.getenv("TEST_JWT_TOKEN", make_token("finance_manager"))
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
MESSAGE = "Research Mezzofy top 3 competitors and output to a text file"
TIMEOUT_S = 180   # Celery worker has up to 3 minutes
POLL_S = 5        # Check every 5 seconds

pytestmark = pytest.mark.integration


class TestResearchMezzofyTask:

    async def test_research_top3_competitors_completes_with_text_file(self):
        """
        Integration: sends research task to live server, polls until done,
        validates completed status + text file artifact in result.

        Requires: server running at TEST_SERVER_URL, Celery worker active,
                  Anthropic API key configured on server.
        """
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as ac:

            # 1. Dispatch task
            resp = await ac.post(
                "/chat/send",
                json={"message": MESSAGE, "platform": "android"},
                headers=HEADERS,
            )
            assert resp.status_code == 202, (
                f"Expected 202, got {resp.status_code}: {resp.text}"
            )
            data = resp.json()
            task_id = data["task_id"]
            assert task_id, "task_id missing from 202 response"
            assert data["status"] == "queued"

            # 2. Poll until completed or timeout
            elapsed = 0
            task = None
            while elapsed < TIMEOUT_S:
                await asyncio.sleep(POLL_S)
                elapsed += POLL_S

                detail = await ac.get(f"/tasks/{task_id}", headers=HEADERS)
                assert detail.status_code == 200
                task = detail.json()

                if task["status"] in ("completed", "failed", "cancelled"):
                    break

            assert task is not None, "No response from polling"
            assert task["status"] == "completed", (
                f"Task did not complete in {TIMEOUT_S}s. "
                f"Final status: {task['status']}. "
                f"Error: {task.get('error')}"
            )

            # 3. Validate result has text file artifact
            result = task.get("result") or {}
            artifacts = result.get("artifacts", [])
            assert len(artifacts) >= 1, "No artifacts in completed task result"

            txt_artifacts = [
                a for a in artifacts
                if a.get("file_type") == "txt"
                or str(a.get("filename", "")).endswith(".txt")
                or str(a.get("name", "")).endswith(".txt")
            ]
            assert len(txt_artifacts) >= 1, (
                f"Expected at least one .txt artifact. Got: {artifacts}"
            )

            # 4. Validate the file is downloadable and non-empty
            txt_art = txt_artifacts[0]
            download_url = txt_art.get("download_url") or f"/files/{txt_art['id']}"
            file_resp = await ac.get(download_url, headers=HEADERS)
            assert file_resp.status_code == 200, (
                f"File download failed: {file_resp.status_code}"
            )
            assert len(file_resp.content) > 0, "Downloaded file is empty"
