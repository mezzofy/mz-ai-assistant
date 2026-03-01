"""
Input handler unit tests — input_router, text_handler, url_handler, image/audio/file handlers.

Tests cover:
  - input_router.process_input routes to correct handler by input_type
  - text_handler passes through message unchanged
  - url_handler._validate_url blocks internal/private IPs
  - url_handler._validate_url allows public URLs
  - url_handler.handle_url returns extracted_text on scrape success
  - url_handler.handle_url returns rejection message on failed validation
  - image_handler, audio_handler, file_handler call correct tool (mocked)
  - Unknown input_type treated as text (passthrough)
  - Speech/camera input_type passthroughs
"""

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.unit


# ── _validate_url unit tests ──────────────────────────────────────────────────

class TestValidateURL:
    """Unit tests for the URL validation logic in url_handler."""

    def _validate(self, url: str) -> str:
        from app.input.url_handler import _validate_url
        return _validate_url(url)

    def test_empty_url_blocked(self):
        assert self._validate("") != ""

    def test_localhost_blocked(self):
        err = self._validate("http://localhost/admin")
        assert err != ""

    def test_loopback_127_blocked(self):
        err = self._validate("http://127.0.0.1:8080/")
        assert err != ""

    def test_ipv6_loopback_blocked(self):
        err = self._validate("http://[::1]/")
        assert err != ""

    def test_aws_metadata_blocked(self):
        err = self._validate("http://169.254.169.254/latest/meta-data/")
        assert err != ""

    def test_rfc1918_10x_blocked(self):
        err = self._validate("http://10.0.0.1/internal")
        assert err != ""

    def test_rfc1918_192168_blocked(self):
        err = self._validate("http://192.168.1.100/api")
        assert err != ""

    def test_rfc1918_172_blocked(self):
        err = self._validate("http://172.16.0.1/")
        assert err != ""

    def test_public_https_allowed(self):
        err = self._validate("https://www.example.com/page")
        assert err == ""

    def test_public_http_allowed(self):
        err = self._validate("http://api.example.com/data")
        assert err == ""

    def test_ftp_scheme_blocked(self):
        err = self._validate("ftp://example.com/file")
        assert err != ""

    def test_file_scheme_blocked(self):
        err = self._validate("file:///etc/passwd")
        assert err != ""

    def test_non_url_blocked(self):
        err = self._validate("not-a-url")
        assert err != ""

    def test_mixed_case_localhost_blocked(self):
        err = self._validate("http://LOCALHOST/admin")
        assert err != ""


# ── handle_url unit tests ─────────────────────────────────────────────────────

class TestHandleURL:
    async def test_valid_url_calls_scraping(self):
        """handle_url calls ScrapingOps.execute for valid URLs."""
        from app.input.url_handler import handle_url

        mock_scraping = AsyncMock()
        mock_scraping.execute = AsyncMock(return_value={
            "success": True,
            "output": "Page title\n\nSome page content about widgets.",
        })

        task = {
            "_config": {"tools": {"browser": {"headless": True}}},
            "url": "https://www.example.com/page",
            "message": "https://www.example.com/page",
        }

        # ScrapingOps is imported lazily inside handle_url — patch at source module
        with patch("app.tools.web.scraping_ops.ScrapingOps", return_value=mock_scraping):
            result = await handle_url(task)

        assert result["input_type"] == "url"
        assert "extracted_text" in result
        assert result["extracted_text"] != ""
        mock_scraping.execute.assert_called_once()

    async def test_invalid_url_returns_rejection(self):
        """handle_url returns rejection message for blocked URLs."""
        from app.input.url_handler import handle_url

        task = {
            "_config": {},
            "url": "http://192.168.1.1/admin",
            "message": "http://192.168.1.1/admin",
        }
        result = await handle_url(task)

        assert result["input_type"] == "url"
        assert "rejected" in result.get("extracted_text", "").lower()

    async def test_scrape_exception_handled_gracefully(self):
        """handle_url handles scraping tool exceptions gracefully."""
        from app.input.url_handler import handle_url

        mock_scraping = AsyncMock()
        mock_scraping.execute = AsyncMock(side_effect=Exception("Connection error"))

        task = {
            "_config": {},
            "url": "https://www.example.com/page",
            "message": "https://www.example.com/page",
        }

        # ScrapingOps is imported lazily inside handle_url — patch at source module
        with patch("app.tools.web.scraping_ops.ScrapingOps", return_value=mock_scraping):
            result = await handle_url(task)

        # Should return partial result, not raise
        assert result["input_type"] == "url"
        assert "extracted_text" in result

    async def test_url_content_truncated_to_max_chars(self):
        """Content longer than _MAX_CONTENT_CHARS (6000) is truncated."""
        from app.input.url_handler import handle_url, _MAX_CONTENT_CHARS

        long_content = "A" * (_MAX_CONTENT_CHARS + 1000)
        mock_scraping = AsyncMock()
        mock_scraping.execute = AsyncMock(return_value={"success": True, "output": long_content})

        task = {
            "_config": {},
            "url": "https://www.example.com",
            "message": "https://www.example.com",
        }

        # ScrapingOps is imported lazily inside handle_url — patch at source module
        with patch("app.tools.web.scraping_ops.ScrapingOps", return_value=mock_scraping):
            result = await handle_url(task)

        # Extracted text must be capped at max chars
        assert len(result.get("extracted_text", "")) <= _MAX_CONTENT_CHARS + 100  # small buffer for prefix


# ── process_input routing tests ───────────────────────────────────────────────

class TestInputRouter:
    """Tests for input_router.process_input dispatch logic."""

    async def test_text_input_routes_to_text_handler(self):
        from app.input.input_router import process_input

        task = {"input_type": "text", "message": "Hello world", "_config": {}}
        with patch("app.input.text_handler.handle_text", new_callable=AsyncMock,
                   return_value={**task, "extracted_text": "Hello world"}) as mock_text:
            result = await process_input(task)

        mock_text.assert_called_once_with(task)
        assert result["extracted_text"] == "Hello world"

    async def test_url_input_routes_to_url_handler(self):
        from app.input.input_router import process_input

        task = {"input_type": "url", "url": "https://example.com", "_config": {}}
        enriched = {**task, "extracted_text": "Page content", "media_content": None, "input_summary": "URL"}
        with patch("app.input.url_handler.handle_url", new_callable=AsyncMock, return_value=enriched) as mock_url:
            result = await process_input(task)

        mock_url.assert_called_once_with(task)

    async def test_image_input_routes_to_image_handler(self):
        from app.input.input_router import process_input

        task = {"input_type": "image", "_config": {}}
        enriched = {**task, "extracted_text": "image content", "media_content": {}, "input_summary": "image"}
        with patch("app.input.image_handler.handle_image", new_callable=AsyncMock, return_value=enriched) as mock_img:
            result = await process_input(task, file_bytes=b"jpeg_data", filename="photo.jpg")

        mock_img.assert_called_once()

    async def test_audio_input_routes_to_audio_handler(self):
        from app.input.input_router import process_input

        task = {"input_type": "audio", "_config": {}}
        enriched = {**task, "extracted_text": "transcript", "media_content": {}, "input_summary": "audio"}
        with patch("app.input.audio_handler.handle_audio", new_callable=AsyncMock, return_value=enriched) as mock_aud:
            result = await process_input(task, file_bytes=b"mp3_data", filename="audio.mp3")

        mock_aud.assert_called_once()

    async def test_file_input_routes_to_file_handler(self):
        from app.input.input_router import process_input

        task = {"input_type": "file", "_config": {}}
        enriched = {**task, "extracted_text": "doc content", "media_content": {}, "input_summary": "file"}
        with patch("app.input.file_handler.handle_file", new_callable=AsyncMock, return_value=enriched) as mock_file:
            result = await process_input(task, file_bytes=b"pdf_data", filename="doc.pdf")

        mock_file.assert_called_once()

    async def test_speech_input_passthrough(self):
        """speech input_type is handled by WebSocket — process_input passes through."""
        from app.input.input_router import process_input

        task = {"input_type": "speech", "message": "transcribed text", "_config": {}}
        result = await process_input(task)

        assert result["extracted_text"] == "transcribed text"
        assert result["media_content"] is None
        assert "speech" in result["input_summary"]

    async def test_camera_input_passthrough(self):
        """camera input_type is handled by WebSocket — process_input passes through."""
        from app.input.input_router import process_input

        task = {"input_type": "camera", "message": "camera frame", "_config": {}}
        result = await process_input(task)

        assert result["extracted_text"] == "camera frame"
        assert "camera" in result["input_summary"]

    async def test_unknown_input_type_treated_as_text(self):
        """Unknown input_type falls back to passthrough."""
        from app.input.input_router import process_input

        task = {"input_type": "hologram", "message": "sci-fi content", "_config": {}}
        result = await process_input(task)

        assert result["extracted_text"] == "sci-fi content"

    async def test_video_input_routes_to_video_handler(self):
        from app.input.input_router import process_input

        task = {"input_type": "video", "_config": {}}
        enriched = {**task, "extracted_text": "video frames", "media_content": {}, "input_summary": "video"}
        with patch("app.input.video_handler.handle_video", new_callable=AsyncMock, return_value=enriched) as mock_vid:
            result = await process_input(task, file_bytes=b"mp4_data", filename="video.mp4")

        mock_vid.assert_called_once()


# ── text_handler unit tests ───────────────────────────────────────────────────

class TestTextHandler:
    async def test_text_handler_passes_message(self):
        """Text handler enriches task with extracted_text = message."""
        from app.input.text_handler import handle_text

        task = {"message": "Hello world", "input_type": "text", "_config": {}}
        result = await handle_text(task)

        assert result["extracted_text"] == "Hello world"
        assert result["input_type"] == "text"

    async def test_text_handler_empty_message(self):
        from app.input.text_handler import handle_text

        task = {"message": "", "input_type": "text", "_config": {}}
        result = await handle_text(task)

        assert "extracted_text" in result

    async def test_text_handler_preserves_task_fields(self):
        """Text handler keeps all original task fields."""
        from app.input.text_handler import handle_text

        task = {
            "message": "test",
            "input_type": "text",
            "_config": {},
            "session_id": "abc-123",
            "role": "sales_rep",
        }
        result = await handle_text(task)

        assert result["session_id"] == "abc-123"
        assert result["role"] == "sales_rep"


# ── image_handler regression tests (BUG-003 / BUG-004) ───────────────────────

class TestImageHandlerBug003:
    """
    Regression tests for BUG-003: image_handler must pass image_bytes (base64)
    to image_ops.execute(), NOT image_path.
    """

    async def test_handle_image_calls_ocr_with_image_bytes(self):
        """handle_image passes base64-encoded bytes to ocr_image, not a file path."""
        from app.input.image_handler import handle_image

        file_bytes = b"\xff\xd8\xff" + b"fake_jpeg_data"
        mock_image_ops = AsyncMock()
        mock_image_ops.execute = AsyncMock(return_value={"success": True, "output": "Invoice #42"})

        task = {"_config": {}, "message": "What is in this image?"}

        with patch("app.tools.media.image_ops.ImageOps", return_value=mock_image_ops):
            result = await handle_image(task, file_bytes, "invoice.jpg")

        # Must have been called with image_bytes kwarg, not image_path
        for call in mock_image_ops.execute.call_args_list:
            kwargs = call.kwargs if call.kwargs else call[1]
            assert "image_path" not in kwargs, (
                "BUG-003 regression: image_handler passed image_path instead of image_bytes"
            )
            assert "image_bytes" in kwargs, (
                "BUG-003 regression: image_handler did not pass image_bytes"
            )

    async def test_handle_image_passes_base64_encoded_bytes(self):
        """image_bytes passed to tools is valid base64 of the original file bytes."""
        import base64
        from app.input.image_handler import handle_image

        file_bytes = b"raw image content 123"
        expected_b64 = base64.b64encode(file_bytes).decode()

        captured_kwargs: dict = {}

        async def capture_execute(operation, **kwargs):
            captured_kwargs.update(kwargs)
            return {"success": True, "output": "description"}

        mock_image_ops = AsyncMock()
        mock_image_ops.execute = capture_execute

        task = {"_config": {}, "message": ""}

        with patch("app.tools.media.image_ops.ImageOps", return_value=mock_image_ops):
            await handle_image(task, file_bytes, "photo.png")

        assert captured_kwargs.get("image_bytes") == expected_b64

    async def test_handle_image_does_not_create_temp_files(self):
        """handle_image no longer writes temp files (BUG-003 fix removes tempfile usage)."""
        import tempfile
        from app.input.image_handler import handle_image

        file_bytes = b"test_bytes"
        mock_image_ops = AsyncMock()
        mock_image_ops.execute = AsyncMock(return_value={"success": False})

        task = {"_config": {}, "message": ""}

        original_mkstemp = tempfile.mkstemp
        temp_files_created = []

        def track_mkstemp(*args, **kwargs):
            result = original_mkstemp(*args, **kwargs)
            temp_files_created.append(result[1])
            return result

        with patch("app.tools.media.image_ops.ImageOps", return_value=mock_image_ops):
            with patch("tempfile.mkstemp", side_effect=track_mkstemp):
                await handle_image(task, file_bytes, "img.jpg")

        assert len(temp_files_created) == 0, (
            "BUG-003 regression: handle_image created temp files it should not"
        )

    async def test_handle_image_builds_extracted_text_from_description_and_ocr(self):
        """extracted_text combines vision description and OCR text."""
        from app.input.image_handler import handle_image

        file_bytes = b"fake_image"

        async def fake_execute(operation, **kwargs):
            if operation == "ocr_image":
                return {"success": True, "output": "TOTAL: $150.00"}
            if operation == "analyze_image":
                return {"success": True, "output": "A photo of a restaurant receipt"}
            return {"success": False}

        mock_image_ops = AsyncMock()
        mock_image_ops.execute = fake_execute

        task = {"_config": {}, "message": "what is the total?"}

        with patch("app.tools.media.image_ops.ImageOps", return_value=mock_image_ops):
            result = await handle_image(task, file_bytes, "receipt.jpg")

        extracted = result["extracted_text"]
        assert "A photo of a restaurant receipt" in extracted
        assert "TOTAL: $150.00" in extracted
        assert "what is the total?" in extracted


class TestManagementAgentBug004:
    """
    Regression tests for BUG-004: ManagementAgent must use extracted_text
    (not raw message) when sending content to the LLM.
    """

    async def test_general_response_uses_extracted_text_when_present(self):
        """_general_response sends extracted_text to LLM, not just message."""
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(config={})
        image_description = "[Image description: A bar chart showing Q1 revenue] Q1 report please"
        task = {
            "message": "Q1 report please",
            "extracted_text": image_description,
            "department": "management",
        }

        captured_messages = []

        async def fake_chat(messages, task_context=None):
            captured_messages.extend(messages)
            return {"content": "Here is your Q1 summary."}

        mock_llm = AsyncMock()
        mock_llm.chat = fake_chat

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        assert len(captured_messages) == 1
        assert captured_messages[0]["content"] == image_description, (
            "BUG-004 regression: agent used task['message'] instead of task['extracted_text']"
        )

    async def test_general_response_falls_back_to_message_when_no_extracted_text(self):
        """_general_response uses task['message'] as fallback when extracted_text is absent."""
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(config={})
        task = {
            "message": "Give me a department overview",
            "department": "management",
        }

        captured_messages = []

        async def fake_chat(messages, task_context=None):
            captured_messages.extend(messages)
            return {"content": "Overview here."}

        mock_llm = AsyncMock()
        mock_llm.chat = fake_chat

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            await agent._general_response(task)

        assert captured_messages[0]["content"] == "Give me a department overview"
