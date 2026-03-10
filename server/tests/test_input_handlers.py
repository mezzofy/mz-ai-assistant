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
        """_general_response passes extracted_text in the task to execute_with_tools."""
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(config={})
        image_description = "[Image description: A bar chart showing Q1 revenue] Q1 report please"
        task = {
            "message": "Q1 report please",
            "extracted_text": image_description,
            "department": "management",
        }

        captured_tasks = []

        async def fake_execute_with_tools(t, **kwargs):
            captured_tasks.append(t)
            return {"content": "Here is your Q1 summary.", "tools_called": [], "artifacts": []}

        mock_llm = AsyncMock()
        mock_llm.execute_with_tools = fake_execute_with_tools

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            result = await agent._general_response(task)

        assert len(captured_tasks) == 1
        assert captured_tasks[0].get("extracted_text") == image_description, (
            "BUG-004 regression: agent did not pass extracted_text to execute_with_tools"
        )

    async def test_general_response_falls_back_to_message_when_no_extracted_text(self):
        """_general_response uses task['message'] as fallback when extracted_text is absent."""
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(config={})
        task = {
            "message": "Give me a department overview",
            "department": "management",
        }

        captured_tasks = []

        async def fake_execute_with_tools(t, **kwargs):
            captured_tasks.append(t)
            return {"content": "Overview here.", "tools_called": [], "artifacts": []}

        mock_llm = AsyncMock()
        mock_llm.execute_with_tools = fake_execute_with_tools

        with patch("app.llm.llm_manager.get", return_value=mock_llm):
            await agent._general_response(task)

        assert len(captured_tasks) == 1
        assert captured_tasks[0].get("message") == "Give me a department overview"


# ── file_handler PDF tests (BUG-A + BUG-B fix) ───────────────────────────────

class TestPDFFileHandler:
    """
    Tests for the PDF extraction path in file_handler._extract_by_extension.

    Covers the two bugs fixed:
      BUG-A: pypdf2 renamed to pypdf — import now works
      BUG-B: tool name was 'extract_text_from_pdf' (non-existent); now 'read_pdf'
    """

    async def test_pdf_calls_read_pdf_not_old_name(self):
        """_extract_by_extension calls PDFOps.execute('read_pdf'), not 'extract_text_from_pdf'."""
        from app.input.file_handler import _extract_by_extension

        captured_ops = []

        async def fake_execute(operation, **kwargs):
            captured_ops.append(operation)
            return {
                "success": True,
                "output": {"pages": [{"text": "Page one text"}], "total_pages": 1},
            }

        mock_pdf_ops = AsyncMock()
        mock_pdf_ops.execute = fake_execute

        with patch("app.tools.document.pdf_ops.PDFOps", return_value=mock_pdf_ops):
            await _extract_by_extension(".pdf", "/tmp/fake.pdf", {})

        assert "read_pdf" in captured_ops, (
            "BUG-B regression: _extract_by_extension did not call read_pdf"
        )
        assert "extract_text_from_pdf" not in captured_ops, (
            "BUG-B regression: _extract_by_extension called the old non-existent tool name"
        )

    async def test_pdf_pages_text_joined_as_string(self):
        """Text from all pages is joined with double newlines and returned as a string."""
        from app.input.file_handler import _extract_by_extension

        async def fake_execute(operation, **kwargs):
            return {
                "success": True,
                "output": {
                    "pages": [
                        {"text": "Introduction paragraph."},
                        {"text": "Second page content."},
                        {"text": "Conclusion."},
                    ],
                    "total_pages": 3,
                },
            }

        mock_pdf_ops = AsyncMock()
        mock_pdf_ops.execute = fake_execute

        with patch("app.tools.document.pdf_ops.PDFOps", return_value=mock_pdf_ops):
            result = await _extract_by_extension(".pdf", "/tmp/fake.pdf", {})

        assert "Introduction paragraph." in result
        assert "Second page content." in result
        assert "Conclusion." in result
        assert isinstance(result, str)

    async def test_pdf_returns_empty_string_on_failure(self):
        """Returns empty string when read_pdf reports success: False."""
        from app.input.file_handler import _extract_by_extension

        async def fake_execute(operation, **kwargs):
            return {"success": False, "output": {}}

        mock_pdf_ops = AsyncMock()
        mock_pdf_ops.execute = fake_execute

        with patch("app.tools.document.pdf_ops.PDFOps", return_value=mock_pdf_ops):
            result = await _extract_by_extension(".pdf", "/tmp/fake.pdf", {})

        assert result == ""


# ── file_handler Files API PDF tests ─────────────────────────────────────────

class TestPDFFilesAPI:
    """
    Tests for the Anthropic Files API primary path in handle_file.

    When the upload succeeds the returned task must contain 'anthropic_file_id'
    and 'extracted_text' must be the user's message (or a default prompt).
    When the upload fails, the handler falls through to the pypdf path.
    """

    async def test_handle_file_pdf_returns_anthropic_file_id_on_success(self):
        """handle_file returns anthropic_file_id when Files API upload succeeds."""
        from app.input.file_handler import handle_file

        fake_file_id = "file_abc123"
        task = {"_config": {"llm": {"claude": {"api_key": "sk-test"}}}, "message": "Summarize this"}

        with patch(
            "app.input.file_handler._upload_pdf_to_files_api_sync",
            return_value=fake_file_id,
        ):
            result = await handle_file(task, b"%PDF fake bytes", "report.pdf")

        assert result.get("anthropic_file_id") == fake_file_id
        assert result.get("extracted_text") == "Summarize this"
        assert result.get("input_type") == "file"

    async def test_handle_file_pdf_default_message_when_no_user_message(self):
        """extracted_text defaults to 'Please analyze this document.' when message is empty."""
        from app.input.file_handler import handle_file

        task = {"_config": {}, "message": ""}

        with patch(
            "app.input.file_handler._upload_pdf_to_files_api_sync",
            return_value="file_xyz",
        ):
            result = await handle_file(task, b"%PDF fake bytes", "doc.pdf")

        assert result.get("extracted_text") == "Please analyze this document."

    async def test_handle_file_pdf_falls_back_to_pypdf_when_upload_fails(self):
        """When Files API upload returns None, handle_file falls through to pypdf."""
        from app.input.file_handler import handle_file

        async def fake_pdf_execute(operation, **kwargs):
            return {
                "success": True,
                "output": {"pages": [{"text": "Fallback pypdf text"}], "total_pages": 1},
            }

        mock_pdf_ops = AsyncMock()
        mock_pdf_ops.execute = fake_pdf_execute

        task = {"_config": {}, "message": "Read this PDF"}

        with patch("app.input.file_handler._upload_pdf_to_files_api_sync", return_value=None), \
             patch("app.tools.document.pdf_ops.PDFOps", return_value=mock_pdf_ops):
            result = await handle_file(task, b"%PDF fake bytes", "fallback.pdf")

        # Must NOT have anthropic_file_id — used the pypdf fallback
        assert "anthropic_file_id" not in result
        # Must contain the extracted pypdf text
        assert "Fallback pypdf text" in result.get("extracted_text", "")

    async def test_handle_file_pdf_input_summary_contains_files_api(self):
        """input_summary mentions Files API when upload succeeds."""
        from app.input.file_handler import handle_file

        task = {"_config": {}, "message": ""}

        with patch(
            "app.input.file_handler._upload_pdf_to_files_api_sync",
            return_value="file_001",
        ):
            result = await handle_file(task, b"%PDF", "whitepaper.pdf")

        assert "Files API" in result.get("input_summary", "")


# ── file_handler Office format tests ──────────────────────────────────────────

class TestFileHandler:
    """Tests for upgraded Office format extraction paths in file_handler."""

    async def test_docx_extraction_includes_table_content(self):
        """DocxOps.read_docx table rows appear in extracted text."""
        from app.input.file_handler import _extract_by_extension

        async def fake_execute(operation, **kwargs):
            return {
                "success": True,
                "output": {
                    "paragraphs": [{"text": "Intro paragraph", "type": "Normal"}],
                    "tables": [
                        {"table_index": 0, "rows": [["Name", "Score"], ["Alice", "95"]]}
                    ],
                },
            }

        mock_docx_ops = AsyncMock()
        mock_docx_ops.execute = fake_execute

        with patch("app.tools.document.docx_ops.DocxOps", return_value=mock_docx_ops):
            result = await _extract_by_extension(".docx", "/tmp/fake.docx", {})

        assert "Intro paragraph" in result
        assert "Alice" in result
        assert "95" in result

    async def test_pptx_extraction_includes_slide_notes(self):
        """PPTXOps.read_pptx speaker notes appear in extracted text."""
        from app.input.file_handler import _extract_by_extension

        async def fake_execute(operation, **kwargs):
            return {
                "success": True,
                "output": {
                    "slide_count": 1,
                    "slides": [
                        {
                            "slide": 1,
                            "text": ["Revenue Overview"],
                            "notes": "Emphasise Q3 growth",
                        }
                    ],
                },
            }

        mock_pptx_ops = AsyncMock()
        mock_pptx_ops.execute = fake_execute

        with patch("app.tools.document.pptx_ops.PPTXOps", return_value=mock_pptx_ops):
            result = await _extract_by_extension(".pptx", "/tmp/fake.pptx", {})

        assert "Revenue Overview" in result
        assert "Emphasise Q3 growth" in result
        assert "[Notes:" in result

    async def test_csv_extraction_uses_500_row_limit_and_numeric_summary(self):
        """CSVOps.read_csv is called with max_rows=500 and numeric summary is included."""
        from app.input.file_handler import _extract_by_extension

        captured_kwargs: dict = {}

        async def fake_execute(operation, **kwargs):
            captured_kwargs.update(kwargs)
            return {
                "success": True,
                "output": {
                    "headers": ["product", "sales"],
                    "rows": [["Widget A", 120], ["Widget B", 85]],
                    "numeric_summary": {
                        "sales": {"min": 85.0, "max": 120.0, "mean": 102.5, "count": 2}
                    },
                },
            }

        mock_csv_ops = AsyncMock()
        mock_csv_ops.execute = fake_execute

        with patch("app.tools.document.csv_ops.CSVOps", return_value=mock_csv_ops):
            result = await _extract_by_extension(".csv", "/tmp/fake.csv", {})

        assert captured_kwargs.get("max_rows") == 500
        assert "product" in result
        assert "Widget A" in result
        assert "[Column Summary]" in result
        assert "sales" in result
        assert "102.50" in result

    async def test_doc_legacy_format_returns_fallback_message(self):
        """Legacy .doc that raises an exception returns a user-friendly fallback message."""
        from app.input.file_handler import _extract_by_extension

        with patch("docx.Document", side_effect=Exception("not a zip file")):
            result = await _extract_by_extension(".doc", "/tmp/legacy.doc", {})

        assert "legacy Word 97-2003" in result
        assert ".docx" in result

    async def test_ppt_legacy_format_returns_fallback_message(self):
        """Legacy .ppt that raises an exception returns a user-friendly fallback message.

        Patches sys.modules so the lazy 'from pptx import Presentation' import fails
        regardless of whether python-pptx is installed in the test environment.
        """
        import sys
        from unittest.mock import patch as _patch
        from app.input.file_handler import _extract_by_extension

        with _patch.dict(sys.modules, {"pptx": None}):
            result = await _extract_by_extension(".ppt", "/tmp/legacy.ppt", {})

        assert "legacy PowerPoint 97-2003" in result
        assert ".pptx" in result
