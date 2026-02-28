"""
Stream Handler — WebSocket connection manager and push helpers.

Manages active WebSocket connections (user_id → WebSocket) so that
Celery task callbacks and agent workflows can push progress updates
to the connected mobile client in real time.

Usage in chat.py:
    from app.output.stream_handler import ws_manager
    await ws_manager.connect(websocket, user_id)
    await ws_manager.send(user_id, {"type": "status", "message": "Analyzing..."})
    await ws_manager.disconnect(user_id)

Usage in Celery tasks (Phase 6):
    from app.output.stream_handler import ws_manager
    await ws_manager.send(user_id, {"type": "task_progress", "progress": 60})
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("mezzofy.output.stream")


class WSConnectionManager:
    """
    In-process WebSocket connection registry.

    Maps user_id → active WebSocket instance. Only one active connection
    per user is maintained (new connection replaces old for same user_id).

    Note: This is an in-process registry. In multi-worker deployments
    (Uvicorn 4 workers), connections to different workers cannot see each
    other. For cross-worker push (e.g., Celery → WebSocket), use Redis
    pub/sub (wired in Phase 6).
    """

    def __init__(self):
        self._connections: dict = {}  # user_id → WebSocket

    async def connect(self, websocket, user_id: str) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        # Cleanly close any existing connection for this user
        old = self._connections.get(user_id)
        if old is not None:
            try:
                await old.close(code=1001, reason="Replaced by new connection")
            except Exception:
                pass
        self._connections[user_id] = websocket
        logger.info(f"WebSocket connected: user={user_id}")

    async def disconnect(self, user_id: str) -> None:
        """Deregister a WebSocket connection."""
        self._connections.pop(user_id, None)
        logger.info(f"WebSocket disconnected: user={user_id}")

    async def send(self, user_id: str, message: dict) -> bool:
        """
        Send a JSON message to a connected user.

        Args:
            user_id: Target user.
            message: JSON-serialisable dict.

        Returns:
            True if sent, False if user is not connected.
        """
        ws = self._connections.get(user_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"WebSocket send failed for user={user_id}: {e}")
            self._connections.pop(user_id, None)
            return False

    def is_connected(self, user_id: str) -> bool:
        return user_id in self._connections

    def active_count(self) -> int:
        return len(self._connections)


# Module-level singleton — imported by chat.py and Celery callbacks
ws_manager = WSConnectionManager()
