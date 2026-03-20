"""
Context Processor — assembles the final API response after agent execution.

Called from chat.py after router.route_request() returns. Performs:
  1. Append user message to conversation history
  2. Append assistant response to conversation history
  3. Register agent-generated artifacts in the DB
  4. Format and return the API response dict

This is the final step before the response is sent back to the mobile app.
"""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.context.session_manager import append_message
from app.context.artifact_manager import register_artifact

logger = logging.getLogger("mezzofy.context.processor")


async def process_result(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    user_message: str,
    agent_result: dict,
    input_summary: str = "",
    department: str = "",
    agent_task_id: str | None = None,
) -> dict:
    """
    Post-process agent execution result and build the API response.

    Args:
        db:           Active DB session (already open from endpoint).
        user_id:      Authenticated user ID.
        session_id:   Conversation session ID (already created/fetched).
        user_message: Original user message text (for history storage).
        agent_result: Dict returned by agent.execute() via router.
        input_summary: Human-readable description of the input type processed.

    Returns:
        API response dict:
          {session_id, response, input_processed, artifacts, agent_used, tools_used, success}
    """
    content = agent_result.get("content", "Task completed.")
    raw_artifacts = agent_result.get("artifacts", []) or []
    tools_called = agent_result.get("tools_called", []) or []
    agent_used = agent_result.get("agent_used", "unknown")
    success = agent_result.get("success", True)

    # 1. Store user message in conversation history.
    # Background tasks (agent_task_id set) pre-save the user message in chat.py
    # immediately after queueing, so we skip it here to avoid a duplicate entry.
    if not agent_task_id:
        try:
            await append_message(db, session_id, "user", user_message)
        except Exception as e:
            logger.warning(f"Failed to store user message (session={session_id}): {e}")

    # 2. Store assistant response in conversation history
    try:
        await append_message(db, session_id, "assistant", content)
    except Exception as e:
        logger.warning(f"Failed to store assistant response (session={session_id}): {e}")

    # 3. Register artifacts in DB and build response list
    response_artifacts = []
    for artifact in raw_artifacts:
        file_path = artifact.get("path", "")
        filename = artifact.get("name", "artifact")
        file_type = artifact.get("type", "file")

        if file_path:
            try:
                db_record = await register_artifact(
                    db=db,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    file_path=file_path,
                    file_type=file_type,
                    scope=artifact.get("scope", "personal"),
                    department=artifact.get("department") or None,
                )
                response_artifacts.append(db_record)
            except Exception as e:
                logger.warning(f"Failed to register artifact '{filename}': {e}")
                # Degrade gracefully — include artifact without DB registration
                response_artifacts.append({
                    "id": None,
                    "filename": filename,
                    "file_type": file_type,
                    "download_url": None,
                })
        else:
            # No file path — artifact record without download URL
            response_artifacts.append({
                "id": None,
                "filename": filename,
                "file_type": file_type,
                "download_url": None,
            })

    # 4. Create or update agent_tasks record
    task_id: str | None = None
    try:
        if agent_task_id:
            # Celery path: UPDATE the existing 'queued'/'running' row to 'completed'.
            # Also store the result JSON (with artifacts) so GET /tasks/{id} can
            # return artifact download URLs without a separate query.
            import json as _json
            _result_payload = _json.dumps({
                "success": success,
                "response": content.strip() if content else "Task completed.",
                "artifacts": [
                    {
                        "id": a.get("id"),
                        "type": a.get("file_type", "file"),
                        "name": a.get("filename", "artifact"),
                        "download_url": a.get("download_url"),
                    }
                    for a in response_artifacts
                ],
            })
            await db.execute(
                text(
                    "UPDATE agent_tasks "
                    "SET status = 'completed', progress = 100, completed_at = NOW(), "
                    "result = CAST(:result AS jsonb), current_step = NULL "
                    "WHERE id = :id"
                ),
                {"result": _result_payload, "id": str(agent_task_id) if agent_task_id is not None else None},
            )
            task_id = agent_task_id
        else:
            # Sync path: INSERT a new completed record
            raw_id = uuid.uuid4()
            task_ref = f"TASK-{str(raw_id)[:8].upper()}"
            await db.execute(
                text(
                    "INSERT INTO agent_tasks "
                    "(id, task_ref, user_id, session_id, department, title, status, progress, started_at, completed_at) "
                    "VALUES (:id, :task_ref, :uid, :sid, :dept, :title, 'completed', 100, NOW(), NOW())"
                ),
                {
                    "id": str(raw_id),
                    "task_ref": task_ref,
                    "uid": user_id,
                    "sid": str(session_id) if session_id is not None else None,
                    "dept": department,
                    "title": user_message[:80],
                },
            )
            task_id = str(raw_id)
    except Exception as e:
        logger.warning(f"Failed to create/update agent_task record (session={session_id}): {e}")
        task_id = agent_task_id  # return the original ID even if DB update failed

    # 5. Build and return formatted API response
    return {
        "session_id": session_id,
        "response": content.strip() if content else "Task completed.",
        "input_processed": {"summary": input_summary} if input_summary else None,
        "artifacts": [
            {
                "id": a.get("id"),
                "type": a.get("file_type", "file"),
                "name": a.get("filename", "artifact"),
                "download_url": a.get("download_url"),
            }
            for a in response_artifacts
        ],
        "agent_used": agent_used,
        "tools_used": tools_called,
        "success": success,
        "task_id": task_id,
    }
