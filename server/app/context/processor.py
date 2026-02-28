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

    # 1. Store user message in conversation history
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

    # 4. Build and return formatted API response
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
    }
