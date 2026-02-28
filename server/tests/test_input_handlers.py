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
