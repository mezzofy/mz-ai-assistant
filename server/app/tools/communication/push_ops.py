"""
Push Notification Tool — Firebase Cloud Messaging (FCM) for mobile push.

Tools provided:
    send_push  — Send push notification to a user's mobile device

Config required (config.yaml → push):
    fcm_credentials_json  — Path to Firebase service account JSON file
      OR
    fcm_server_key        — FCM legacy server key (deprecated but supported)

Used when:
    - Long-running tasks complete ("Your pitch deck is ready")
    - Scheduled reports are delivered
    - Webhook events trigger user notifications
    - Agent tasks finish in background
"""

import logging
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.push")


class PushOps(BaseTool):
    """Mobile push notification operations via Firebase Cloud Messaging."""

    def __init__(self, config: dict):
        super().__init__(config)
        push_cfg = config.get("push", {})
        self._credentials_json: str = push_cfg.get("fcm_credentials_json", "")
        self._server_key: str = push_cfg.get("fcm_server_key", "")
        self._app_name: str = push_cfg.get("app_name", "mezzofy-ai")
        self._initialized = False

    def _init_firebase(self) -> None:
        """Initialize Firebase Admin SDK (once)."""
        if self._initialized:
            return

        import firebase_admin
        from firebase_admin import credentials

        # Check if already initialized under this app name
        try:
            firebase_admin.get_app(self._app_name)
            self._initialized = True
            return
        except ValueError:
            pass  # Not yet initialized

        if self._credentials_json:
            import json
            import os
            cred_path = self._credentials_json
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            else:
                # Treat as JSON string
                cred_dict = json.loads(self._credentials_json)
                cred = credentials.Certificate(cred_dict)
        else:
            # Fall back to application default credentials
            cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(cred, name=self._app_name)
        self._initialized = True

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "send_push",
                "description": (
                    "Send a push notification to a user's mobile device via Firebase Cloud Messaging. "
                    "Use this to alert users when tasks complete, reports are ready, or important "
                    "events occur. Requires the user's FCM device token."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_token": {
                            "type": "string",
                            "description": "FCM device registration token for the user's mobile device.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Notification title shown on the device.",
                        },
                        "body": {
                            "type": "string",
                            "description": "Notification body text shown on the device.",
                        },
                        "data": {
                            "type": "object",
                            "description": (
                                "Optional key-value pairs sent as data payload to the app "
                                "(e.g., {\"action\": \"open_artifact\", \"artifact_id\": \"123\"})."
                            ),
                            "additionalProperties": {"type": "string"},
                        },
                        "image_url": {
                            "type": "string",
                            "description": "Optional URL of an image to display in the notification.",
                        },
                    },
                    "required": ["device_token", "title", "body"],
                },
                "handler": self._send_push,
            },
        ]

    async def _send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
        image_url: Optional[str] = None,
    ) -> dict:
        """Send a push notification via FCM."""
        if not self._credentials_json and not self._server_key:
            return self._err("Push notification credentials are not configured (push.fcm_credentials_json).")

        try:
            self._init_firebase()

            from firebase_admin import messaging

            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url,
            )

            # Ensure data values are all strings (FCM requirement)
            string_data: dict[str, str] = {}
            if data:
                string_data = {k: str(v) for k, v in data.items()}

            message = messaging.Message(
                token=device_token,
                notification=notification,
                data=string_data if string_data else None,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        icon="notification_icon",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound="default",
                            badge=1,
                        )
                    )
                ),
            )

            import asyncio
            import firebase_admin
            app = firebase_admin.get_app(self._app_name)
            loop = asyncio.get_event_loop()
            message_id = await loop.run_in_executor(None, lambda: messaging.send(message, app=app))
            logger.info(f"Push notification sent: {message_id} → '{title}'")

            return self._ok({
                "message_id": message_id,
                "title": title,
                "body": body,
            })

        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return self._err(str(e))


async def log_notification(user_id: str, title: str, body: str, data: Optional[dict] = None) -> None:
    """
    Insert one row into notification_log for the given user.
    Fails silently — never raises; logs a warning on error.
    """
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text as _text
        import json as _json
        data_json = _json.dumps(data) if data else None
        async with AsyncSessionLocal() as db:
            await db.execute(
                _text("""
                    INSERT INTO notification_log (user_id, title, body, data)
                    VALUES (:uid, :title, :body, :data::jsonb)
                """),
                {"uid": user_id, "title": title, "body": body, "data": data_json},
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"log_notification failed for user={user_id}: {e}")


async def get_user_push_targets(user_id: str) -> list[dict]:
    """
    Return registered FCM targets for a user, respecting push_notifications_enabled.
    Returns [] if no devices, preference OFF, or DB error (fail silently).
    """
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text as _text
        async with AsyncSessionLocal() as db:
            pref = await db.execute(
                _text("SELECT push_notifications_enabled FROM users WHERE id = :uid"),
                {"uid": user_id},
            )
            pref_row = pref.fetchone()
            if pref_row is None or not pref_row.push_notifications_enabled:
                return []
            tokens = await db.execute(
                _text("SELECT device_token, platform FROM user_devices WHERE user_id = :uid"),
                {"uid": user_id},
            )
            return [{"device_token": r.device_token, "platform": r.platform}
                    for r in tokens.fetchall()]
    except Exception as e:
        logger.warning(f"get_user_push_targets failed for user={user_id}: {e}")
        return []


async def send_push(
    user_id: str,
    device_token: str,
    platform: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict:
    """
    Standalone push helper callable from Celery tasks.

    Wraps PushOps._send_push(). Platform is logged but FCM handles both
    iOS (APNs via FCM) and Android transparently — no separate code path needed.

    Returns:
        {"success": bool, "message_id": str | None}
    """
    from app.core.config import get_config
    config = get_config()
    ops = PushOps(config)
    result = await ops._send_push(
        device_token=device_token,
        title=title,
        body=body,
        data=data,
    )
    logger.info(
        f"send_push: user={user_id} platform={platform} "
        f"success={result.get('success')} msg={result.get('output', {}).get('message_id')}"
    )
    if result.get("success"):
        await log_notification(user_id=user_id, title=title, body=body, data=data)
    # NOTE: webhook_tasks.py calls PushOps._send_push() directly and does not go
    # through this function — that path does not log to notification_log in v1.30.0.
    return {
        "success": result.get("success", False),
        "message_id": result.get("output", {}).get("message_id"),
    }
