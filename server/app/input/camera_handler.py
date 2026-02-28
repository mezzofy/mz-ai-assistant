"""
Camera Handler — processes live camera frames from the mobile app.

Called from the WebSocket handler in chat.py at ~1 fps.
Each call analyzes a single base64-encoded JPEG frame via ImageOps.

This is NOT routed through input_router.py — it is called directly
from the WebSocket loop on every camera_frame message.
"""

import base64
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger("mezzofy.input.camera")


async def handle_camera_frame(frame_b64: str, config: dict) -> dict:
    """
    Analyze a single camera frame received over WebSocket.

    Args:
        frame_b64: Base64-encoded JPEG image bytes.
        config:    App config dict (for ImageOps).

    Returns:
        {
            "success": bool,
            "description": str,  — vision analysis of the frame
        }
    """
    # Decode base64
    try:
        frame_bytes = base64.b64decode(frame_b64)
    except Exception as e:
        logger.warning(f"Failed to decode camera frame: {e}")
        return {"success": False, "description": "Invalid frame data"}

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(frame_bytes)
            tmp_path = tmp.name

        from app.tools.media.image_ops import ImageOps
        image_ops = ImageOps(config)

        result = await image_ops.execute("analyze_image", image_path=tmp_path)
        if result.get("success"):
            return {"success": True, "description": result.get("output", "")}
        return {"success": False, "description": "Frame analysis failed"}

    except Exception as e:
        logger.warning(f"Camera frame analysis error: {e}")
        return {"success": False, "description": str(e)}

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
