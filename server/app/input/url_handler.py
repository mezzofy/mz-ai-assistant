"""
URL Handler — fetches and processes web page content.

Uses ScrapingOps (Phase 3) for text extraction.
Validates URL format and blocks internal/loopback addresses before fetching.
"""

import logging
from urllib.parse import urlparse

logger = logging.getLogger("mezzofy.input.url")

# Block patterns for internal/unsafe hosts
_BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0",
    "169.254.169.254",  # AWS metadata endpoint
    "::1",
}

# Max characters from scraped page to include in extracted_text
_MAX_CONTENT_CHARS = 6000


async def handle_url(task: dict) -> dict:
    """
    Fetch a URL and extract text content for the LLM.

    The URL is taken from task["url"] if present, otherwise from task["message"].

    Args:
        task: Task dict with _config, url (optional), and message.

    Returns:
        Task dict enriched with extracted_text containing the page content.
    """
    config = task.get("_config", {})
    url = (task.get("url") or task.get("message", "")).strip()

    # Validate
    validation_error = _validate_url(url)
    if validation_error:
        logger.warning(f"URL rejected: {validation_error} — {url!r}")
        return {
            **task,
            "input_type": "url",
            "extracted_text": f"[URL rejected: {validation_error}]",
            "media_content": None,
            "input_summary": f"URL: {url} (rejected — {validation_error})",
        }

    # Scrape
    from app.tools.web.scraping_ops import ScrapingOps
    scraping = ScrapingOps(config)

    content = ""
    try:
        result = await scraping.execute("scrape_text", url=url)
        if result.get("success"):
            content = (result.get("output") or "").strip()[:_MAX_CONTENT_CHARS]
    except Exception as e:
        logger.warning(f"Scraping failed for {url!r}: {e}")

    user_msg = (task.get("message") or "").strip()
    # Only include user message separately if it's not the same as the URL
    user_addendum = user_msg if user_msg and user_msg != url else ""

    parts = []
    if content:
        parts.append(f"[Web page content from {url}:\n{content}]")
    else:
        parts.append(f"[URL content could not be fetched: {url}]")
    if user_addendum:
        parts.append(user_addendum)

    return {
        **task,
        "input_type": "url",
        "extracted_text": "\n\n".join(parts),
        "media_content": {"url": url, "content": content},
        "input_summary": (
            f"URL: {url} ({len(content):,} chars scraped)"
            if content
            else f"URL: {url} (fetch failed)"
        ),
    }


def _validate_url(url: str) -> str:
    """
    Validate URL format and block internal/dangerous hosts.
    Returns empty string if valid, or an error message if invalid.
    """
    if not url:
        return "empty URL"

    try:
        parsed = urlparse(url)
    except Exception:
        return "malformed URL"

    if parsed.scheme not in ("http", "https"):
        return f"unsupported scheme: {parsed.scheme!r}"

    host = (parsed.hostname or "").lower()
    if not host:
        return "missing host"

    if host in _BLOCKED_HOSTS:
        return f"blocked host: {host}"

    # Block 10.x, 172.16-31.x, 192.168.x internal ranges (simple check)
    if (
        host.startswith("10.")
        or host.startswith("192.168.")
        or any(host.startswith(f"172.{n}.") for n in range(16, 32))
    ):
        return f"blocked private network: {host}"

    return ""
