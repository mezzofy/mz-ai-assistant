"""
LLMManager — Central orchestrator for Claude + Kimi LLM backends.

Responsibilities:
  - Routes requests: Chinese content → Kimi, everything else → Claude
  - Manages the agentic tool-calling loop (≤5 iterations)
  - Auto-failover: if primary model fails, retry on other
  - Tracks token usage per model/department/user → llm_usage table
  - Builds department-aware system prompts

Called by:
  - Chat API (Phase 5): mobile user messages via REST/WebSocket
  - Agent workflows (Phase 4): agents call execute_with_tools() directly
  - Scheduler / Webhook tasks (Phase 6): automated background tasks

Config section: config["llm"]
"""

import asyncio
import logging
import re
import unicodedata
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from app.llm.anthropic_client import AnthropicClient
from app.llm.kimi_client import KimiClient
from app.tools.tool_executor import ToolExecutor

logger = logging.getLogger("mezzofy.llm.manager")

# ── Module-level singleton ─────────────────────────────────────────────────────

_manager: Optional["LLMManager"] = None


def init(config: dict) -> None:
    """Initialize the module-level LLMManager singleton. Call once at startup."""
    global _manager
    _manager = LLMManager(config)
    logger.info("LLMManager singleton initialized")


def get() -> "LLMManager":
    """Return the singleton LLMManager instance."""
    if _manager is None:
        raise RuntimeError(
            "LLMManager not initialized — call llm_manager.init(config) first"
        )
    return _manager

# Maximum tool-calling loop iterations
MAX_TOOL_ITERATIONS = 5

# ── Anthropic server-side tool definitions (module-level constants) ────────────

WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    # No user_location needed — Anthropic handles it
}

WEB_FETCH_TOOL = {
    "type": "web_fetch_20250124",
    "name": "web_fetch",
}

CODE_EXECUTION_TOOL = {
    "type": "code_execution_20250825",
    "name": "code_execution",
}

MEMORY_TOOL = {
    "type": "memory",
    "name": "memory",
}

SKILLS_BETAS = ["code-execution-2025-08-25", "skills-2025-10-02"]

SKILL_CONFIGS = {
    "pptx": {"type": "anthropic", "skill_id": "pptx", "version": "latest"},
    "xlsx": {"type": "anthropic", "skill_id": "xlsx", "version": "latest"},
    "pdf":  {"type": "anthropic", "skill_id": "pdf",  "version": "latest"},
    "docx": {"type": "anthropic", "skill_id": "docx", "version": "latest"},
}

# Singapore timezone (UTC+8) — used for current_time injection in system prompt
_SGT = timezone(timedelta(hours=8))


def _map_scope(s: str) -> str:
    """Map tool storage_scope values to DB scope values."""
    return "personal" if s == "user" else s

# System prompt template — filled with department/role/source/save_options at runtime
_SYSTEM_PROMPT_TEMPLATE = """You are the Mezzofy AI Assistant helping the {department} team.

You have access to tools for:
- Sending emails via Outlook (Microsoft Graph API)
- Creating/reading calendar events in Outlook
- Posting messages to MS Teams channels
- Generating PDFs, slide decks, and Word documents
- Searching the web and LinkedIn for company and contact research
- Querying Mezzofy's internal data (products, pricing, features, case studies)
- Managing the CRM / sales lead database
- Querying financial, support ticket, and operational databases
- Processing and analyzing images, audio, and video files
- Accessing YOUR personal Microsoft account (email, calendar, OneNote, Teams chats, Contacts)
  if you have connected it in Settings → Connected Accounts

Department context: {department}
User role: {role}
Task source: {source}
Current date: {current_date}
Current time: {current_time}
Current user ID: {user_id}
(Use this exact value for the user_id parameter in all personal_* tool calls)

Be professional, concise, and action-oriented. When generating customer-facing content, use Mezzofy brand voice (confident, friendly, professional). When sending emails via Outlook, always confirm with the user before sending unless they explicitly said "auto send" or this is a scheduled/webhook task (auto-send is allowed for automated workflows).

When delivering scheduled report results, format output clearly for MS Teams with headings and attach generated files.

IMPORTANT — File storage rule:
If the user has NOT specified where to save the file in their message, you MUST ask:
"{save_options}"
If the user has already stated a storage location (e.g., "personal folder", "my files",
"shared folder", "team folder", "company folder"), use that location directly and skip
this question. Personal/mine/me → storage_scope="user". Shared/team/department →
storage_scope="department". Company/everyone/all staff → storage_scope="company".

FILE SEARCH RULE:
When the user asks about information that might be in their documents or files
(e.g. "check the SLA", "what does our pricing doc say", "find our contract terms",
"look up our policy on X"), you MUST call search_user_files(query=<topic>) FIRST
to discover relevant files, then call read_pdf / read_txt / read_csv on the returned
file_path(s) to extract the content, then answer based on what you find. Do not ask
the user to provide a file path — discover it yourself. If no files are found, respond:
"I couldn't find any documents matching '<topic>' in your accessible folders." """

# Appended to system prompt when a document is already in the conversation context
_ATTACHED_FILE_DIRECTIVE = """

ATTACHED DOCUMENT:
The user has provided a document as a native file attachment (Anthropic Files API).
It is already present in this conversation as a document block — Claude can read it
directly. Do NOT call read_pdf, read_txt, search_user_files, or any extraction tool
for the attached document. The FILE SEARCH RULE above applies only when the user
references documents that are NOT already in this conversation."""

# Appended to system prompt when an image is attached via Files API
_ATTACHED_IMAGE_DIRECTIVE = """

ATTACHED IMAGE:
The user has provided an image as a native file attachment (Anthropic Files API).
It is already present in this conversation as an image block — Claude can see it
directly. Do NOT call analyze_image, ocr_image, or any image processing tool
for the attached image. Answer based on what you can see in the image directly."""


class LLMManager:
    """
    Orchestrates Claude and Kimi LLM calls with routing, tool use, and failover.
    """

    def __init__(self, config: dict):
        self.config = config
        self.claude = AnthropicClient(config)
        self.kimi = KimiClient(config)
        self.tool_executor = ToolExecutor(config)
        logger.info("LLMManager ready (Claude + Kimi)")

    # ── Public API ────────────────────────────────────────────────────────────

    def select_model(self, message: str, context: Optional[dict] = None) -> object:
        """
        Select the appropriate LLM backend for this request.

        Routing rules (in order):
          1. Chinese characters in message → Kimi
          2. APAC / Chinese market signals in context → Kimi
          3. Everything else → Claude

        Args:
            message: The user's message text.
            context: Optional task context dict (may include "department", "source", etc.)

        Returns:
            AnthropicClient or KimiClient instance.
        """
        if self._contains_chinese(message):
            logger.debug("select_model: Chinese content detected → Kimi")
            return self.kimi

        if context and self._is_chinese_market_task(message, context):
            logger.debug("select_model: APAC/Chinese market task detected → Kimi")
            return self.kimi

        logger.debug("select_model: default → Claude")
        return self.claude

    async def chat(
        self,
        messages: list[dict],
        task_context: Optional[dict] = None,
        stream: bool = False,
    ) -> dict:
        """
        Simple single-turn or multi-turn chat without tool calling.

        Args:
            messages: Conversation history.
            task_context: {department, role, source} for system prompt.
            stream: If True, returns streaming response (for WebSocket).

        Returns:
            Normalized response dict from the selected model.
        """
        system = self._build_system_prompt(task_context)
        last_message = messages[-1]["content"] if messages else ""
        model = self.select_model(last_message, task_context)

        try:
            return await model.chat(messages, system=system)
        except Exception as primary_err:
            logger.warning(
                f"LLMManager.chat: primary model ({model.model_name}) failed: {primary_err} — failing over"
            )
            fallback = self.kimi if model is self.claude else self.claude
            return await fallback.chat(messages, system=system)

    async def execute_with_tools(
        self,
        task: dict,
        tool_names: Optional[list[str]] = None,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> dict:
        """
        Run the agentic tool-calling loop.

        Selects model, calls it with tool definitions, executes any requested tools,
        feeds results back, and repeats until the model returns a final answer
        or the max iterations limit is reached.

        Args:
            task: Task dict containing at minimum:
                  - "message": str — user's request
                  - "messages": list[dict] — conversation history (optional)
                  - "department": str — for system prompt
                  - "role": str — user role
                  - "source": str — "mobile" | "scheduler" | "webhook"
                  - "user_id": str — for usage tracking
            tool_names: Subset of tool names to expose. None = all registered tools.
            max_iterations: Hard cap on tool-calling rounds. Default: 5.

        Returns:
            {
                "success": bool,
                "content": str,         # Final LLM response text
                "iterations": int,      # Number of tool-calling rounds used
                "tools_called": list,   # Names of tools invoked
                "usage": {              # Aggregate token usage
                    "input_tokens": int,
                    "output_tokens": int,
                    "model": str,
                },
            }
        """
        message = task.get("extracted_text") or task.get("message", "")
        model = self.select_model(message, task)
        system = self._build_system_prompt(task)
        logger.info(
            f"execute_with_tools: user_id={task.get('user_id')} "
            f"dept={task.get('department')} model={model.model_name} "
            f"msg_len={len(message)}"
        )

        # Build initial message list
        history = list(task.get("messages", []))
        file_id = task.get("anthropic_file_id")
        if file_id:
            if task.get("input_type") == "image":
                # Pass image to Claude as a native image block (Files API)
                user_content = [
                    {"type": "image", "source": {"type": "file", "file_id": file_id}},
                    {"type": "text", "text": message or "Please analyze this image."},
                ]
            else:
                # Pass document (PDF) to Claude as a native document block (Files API)
                user_content = [
                    {"type": "document", "source": {"type": "file", "file_id": file_id}},
                    {"type": "text", "text": message or "Please analyze this document."},
                ]
            history.append({"role": "user", "content": user_content})
        else:
            if not history or history[-1].get("content") != message:
                history.append({"role": "user", "content": message})

        # Get tool definitions
        all_tool_defs = self.tool_executor.get_all_definitions()
        if tool_names:
            tool_defs = [t for t in all_tool_defs if t["name"] in tool_names]
        else:
            tool_defs = all_tool_defs

        total_usage = {"input_tokens": 0, "output_tokens": 0}
        tools_called: list[str] = []
        artifacts: list[dict] = []
        iterations = 0
        used_model = model
        callback = task.get("_progress_callback")

        for i in range(max_iterations):
            iterations = i + 1

            # Report "thinking" step before each LLM call
            if callback:
                await callback(tool=None, iteration=iterations, max_iter=max_iterations)

            try:
                response = await model.chat(history, tools=tool_defs, system=system)
            except Exception as primary_err:
                logger.warning(
                    f"LLMManager tool loop iter={iterations}: primary model "
                    f"({model.model_name}) failed: {primary_err!r} — trying fallback"
                )
                try:
                    fallback = self.kimi if model is self.claude else self.claude
                    response = await fallback.chat(history, tools=tool_defs, system=system)
                    used_model = fallback
                except Exception as fallback_err:
                    logger.error(
                        f"LLMManager tool loop iter={iterations}: both models failed — "
                        f"primary={primary_err!r} fallback={fallback_err!r}"
                    )
                    # If tools already executed successfully, tell the user what was done
                    # rather than returning a generic error. The artifacts must be included
                    # so process_result() can register them in the DB.
                    if artifacts:
                        files_created = ", ".join(a["name"] for a in artifacts)
                        content = (
                            f"Your file(s) have been saved: {files_created}. "
                            f"Please check your Files tab."
                        )
                    else:
                        content = "AI service is temporarily unavailable. Please try again shortly."
                    return {
                        "success": False,
                        "content": content,
                        "iterations": iterations,
                        "tools_called": tools_called,
                        "artifacts": artifacts,          # so process_result() registers them
                        "usage": {**total_usage, "model": model.model_name},
                    }

            # Accumulate token usage
            usage = response.get("usage", {})
            total_usage["input_tokens"] += usage.get("input_tokens", 0)
            total_usage["output_tokens"] += usage.get("output_tokens", 0)

            # No tool calls → final answer
            if not response.get("tool_calls"):
                # Track usage asynchronously (non-blocking, non-fatal)
                asyncio.create_task(self._track_usage(
                    model_name=used_model.model_name,
                    department=task.get("department", "unknown"),
                    user_id=task.get("user_id", "system"),
                    input_tokens=total_usage["input_tokens"],
                    output_tokens=total_usage["output_tokens"],
                ))
                return {
                    "success": True,
                    "content": response["content"],
                    "iterations": iterations,
                    "tools_called": tools_called,
                    "artifacts": artifacts,
                    "usage": {**total_usage, "model": used_model.model_name},
                }

            # Execute requested tools
            tool_calls = response["tool_calls"]
            tool_results = []

            for tc in tool_calls:
                tool_name = tc["name"]
                tools_called.append(tool_name)
                logger.info(f"LLMManager: executing tool '{tool_name}' (iteration {iterations})")

                # Report tool call before execution
                if callback:
                    await callback(tool=tool_name, iteration=iterations, max_iter=max_iterations)

                try:
                    result = await self.tool_executor.execute(tool_name, **tc["arguments"])
                except Exception as tool_err:
                    logger.error(
                        f"LLMManager: tool '{tool_name}' raised exception: {tool_err!r} "
                        f"(user={task.get('user_id')} iter={iterations})"
                    )
                    # Return immediately — do NOT feed this back to the model as a tool result,
                    # which would trigger another (likely failing) model API call.
                    return {
                        "success": False,
                        "content": f"Tool '{tool_name}' failed: {tool_err}",
                        "iterations": iterations,
                        "tools_called": tools_called,
                        "artifacts": artifacts,
                        "usage": {**total_usage, "model": used_model.model_name},
                    }

                tool_results.append((tc, result))

                # If the tool created a file, capture its metadata
                output = result.get("output", {})
                if isinstance(output, dict) and output.get("file_path") and output.get("filename"):
                    fname = output["filename"]
                    file_type = fname.rsplit(".", 1)[-1] if "." in fname else "file"
                    artifacts.append({
                        "name": fname,
                        "path": output["file_path"],
                        "type": file_type,
                        "scope": _map_scope(output.get("storage_scope", "user")),
                        "department": output.get("department", ""),
                    })

            # Append assistant message with tool calls + tool result messages to history
            history = self._append_tool_exchange(
                model=used_model,
                history=history,
                tool_calls=tool_calls,
                tool_results=tool_results,
            )

        # Reached max iterations without final answer
        logger.warning(
            f"LLMManager: reached max iterations ({max_iterations}) — returning partial answer"
        )
        asyncio.create_task(self._track_usage(
            model_name=used_model.model_name,
            department=task.get("department", "unknown"),
            user_id=task.get("user_id", "system"),
            input_tokens=total_usage["input_tokens"],
            output_tokens=total_usage["output_tokens"],
        ))
        return {
            "success": True,
            "content": f"I completed {len(tools_called)} steps but reached the maximum action limit. "
                       f"Tools used: {', '.join(tools_called) if tools_called else 'none'}. "
                       f"Please narrow your request or try again.",
            "iterations": iterations,
            "tools_called": tools_called,
            "artifacts": artifacts,
            "usage": {**total_usage, "model": used_model.model_name},
        }

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream_response(self, task: dict):
        """
        Stream a response token by token for WebSocket delivery.

        Yields str chunks. Does NOT support tool calling (streaming + tools
        are handled in Phase 5 via the WebSocket handler).
        """
        message = task.get("message", "")
        model = self.select_model(message, task)
        system = self._build_system_prompt(task)
        messages = task.get("messages", [{"role": "user", "content": message}])

        try:
            async for chunk in model.stream_chat(messages, system=system):
                yield chunk
        except Exception as e:
            logger.error(f"LLMManager.stream_response failed: {e}")
            yield f"\n[Error: streaming failed — {e}]"

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_system_prompt(self, task: Optional[dict]) -> str:
        """Build department-aware system prompt from task context.

        If task contains a "system_prompt" key, it is returned as-is.
        This allows specialist agents (e.g. SchedulerAgent) to inject a
        fully custom prompt without going through the department template.
        """
        if task and task.get("system_prompt"):
            return task["system_prompt"]

        dept = (task or {}).get("department", "General")
        role = (task or {}).get("role", "user")
        source = (task or {}).get("source", "mobile")
        user_id = (task or {}).get("user_id", "")

        if dept.lower() == "management" or role.lower() in ("admin", "superadmin"):
            save_options = (
                f"Where would you like to save this file?\n"
                f"  (1) Your personal folder — only visible to you\n"
                f"  (2) The {dept} shared department folder — visible to your whole team\n"
                f"  (3) The company-wide public folder — visible to all staff\n"
                f'Wait for their reply. If they choose (1) or say "personal/mine/me", call with storage_scope="user". '
                f'If they choose (2) or say "shared/team/department/{dept}", call with storage_scope="department". '
                f'If they choose (3) or say "company/everyone/all staff", call with storage_scope="company". '
                f"Do not skip this question."
            )
        else:
            save_options = (
                f"Where would you like to save this file?\n"
                f"  (1) Your personal folder — only visible to you\n"
                f"  (2) The {dept} shared department folder — visible to your whole team\n"
                f'Wait for their reply. If they choose (1) or say "personal/mine/me", call with storage_scope="user". '
                f'If they choose (2) or say "shared/team/department/{dept}", call with storage_scope="department". '
                f"Do not skip this question."
            )

        prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            department=dept,
            role=role,
            source=source,
            save_options=save_options,
            user_id=user_id,
            current_date=date.today().strftime("%B %d, %Y"),
            current_time=datetime.now(_SGT).strftime("%I:%M %p SGT"),
        )

        # If a file/image was attached via Files API, tell Claude not to call extraction tools
        if (task or {}).get("anthropic_file_id"):
            if (task or {}).get("input_type") == "image":
                prompt += _ATTACHED_IMAGE_DIRECTIVE
            else:
                prompt += _ATTACHED_FILE_DIRECTIVE

        return prompt

    def _contains_chinese(self, text: str) -> bool:
        """
        Return True if the text contains Chinese characters
        (Simplified or Traditional CJK Unified Ideographs).
        """
        for char in text:
            name = unicodedata.name(char, "")
            if "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name:
                return True
        # Also check Unicode ranges directly
        return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", text))

    def _is_chinese_market_task(self, message: str, context: dict) -> bool:
        """
        Return True if the task is oriented toward Chinese market / APAC research.
        Checked when no Chinese characters are present in the message.
        """
        apac_signals = {
            "china", "chinese market", "mainland", "apac",
            "mandarin", "中国", "亚太", "新加坡"
        }
        msg_lower = message.lower()
        if any(signal in msg_lower for signal in apac_signals):
            return True

        # Check context for APAC routing signals
        department = context.get("department", "").lower()
        return department in ("apac", "china", "asia")

    def _append_tool_exchange(
        self,
        model: object,
        history: list[dict],
        tool_calls: list[dict],
        tool_results: list[tuple],
    ) -> list[dict]:
        """
        Append the assistant's tool calls and tool results to the conversation history.

        Handles format differences between Anthropic (content blocks) and OpenAI (tool_calls array).
        """
        if model is self.claude:
            # Anthropic format: assistant message with tool_use content blocks
            assistant_content = []
            for tc in tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["arguments"],
                })
            history.append({"role": "assistant", "content": assistant_content})

            # Tool results: single user message with tool_result blocks
            result_content = []
            for tc, result in tool_results:
                content = result.get("output") or result.get("error") or ""
                if not isinstance(content, str):
                    import json
                    content = json.dumps(content)
                result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": content,
                })
            history.append({"role": "user", "content": result_content})

        else:
            # OpenAI/Kimi format: assistant message with tool_calls array
            openai_tool_calls = []
            import json
            for tc in tool_calls:
                openai_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"]),
                    },
                })
            history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": openai_tool_calls,
            })

            # Individual tool result messages
            for tc, result in tool_results:
                content = result.get("output") or result.get("error") or ""
                if not isinstance(content, str):
                    content = json.dumps(content)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["name"],
                    "content": content,
                })

        return history

    async def _track_usage(
        self,
        model_name: str,
        department: str,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Insert token usage record into llm_usage table.
        Non-fatal — failures are logged but do not affect the response.
        """
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text

            sql = """
                INSERT INTO llm_usage
                    (model, department, user_id, input_tokens, output_tokens)
                VALUES
                    (:model, :department, :user_id, :input_tokens, :output_tokens)
            """
            async with AsyncSessionLocal() as session:
                await session.execute(text(sql), {
                    "model": model_name,
                    "department": department,
                    "user_id": user_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                })
                await session.commit()
        except Exception as e:
            logger.warning(f"_track_usage failed (non-fatal): {e}")

    # ── Extended LLM methods using Anthropic native capabilities ──────────────

    async def research_with_web_tools(
        self,
        query: str,
        task_context: dict,
        fetch_urls: list = None,
        use_code_execution: bool = False,
    ) -> dict:
        """
        Use Anthropic's native web_search + web_fetch server tools for research.
        REPLACES: browser_ops.search_web() and scraping_ops.scrape_url()
        for research-type tasks.

        browser_ops / scraping_ops remain for:
          - LinkedIn scraping (requires authenticated session cookie)
          - Internal URL scraping (intranet, localhost)
          - Playwright-specific interactions (click, fill form, screenshot)

        Args:
            query:              Research query or instruction
            task_context:       Agent task dict (for system prompt + user context)
            fetch_urls:         Specific URLs to fetch (optional, in addition to search)
            use_code_execution: Enable code execution for data processing

        Returns:
            {
              text: str,           # Research findings
              sources: list[dict], # [{title, url, snippet}] from web_search results
              usage: dict,
            }
        """
        server_tools = [WEB_SEARCH_TOOL, WEB_FETCH_TOOL]
        if use_code_execution:
            server_tools.append(CODE_EXECUTION_TOOL)

        # Build the research prompt
        user_content = query
        if fetch_urls:
            url_list = "\n".join(f"- {u}" for u in fetch_urls)
            user_content += f"\n\nAlso fetch and analyse these specific URLs:\n{url_list}"

        messages = [{"role": "user", "content": user_content}]
        system = self._build_system_prompt(task_context)

        # NOTE: web_search + web_fetch are GA — no beta header needed
        result = await self.claude.chat_with_server_tools(
            messages=messages,
            server_tools=server_tools,
            system=system,
        )

        # Extract source citations from server tool result blocks
        sources = self._extract_web_sources(result["content"])

        # Track usage in llm_usage table
        asyncio.create_task(self._track_usage_extended(
            model_name="claude-sonnet-4-6",
            department=task_context.get("department", "unknown"),
            user_id=task_context.get("user_id"),
            agent_id=task_context.get("agent_id"),
            input_tokens=result["usage"]["input_tokens"],
            output_tokens=result["usage"]["output_tokens"],
            server_tools_used=["web_search", "web_fetch"],
            betas_used=[],
        ))

        return {
            "text":    result["text"],
            "sources": sources,
            "usage":   result["usage"],
        }

    def _extract_web_sources(self, content_blocks: list) -> list:
        """
        Parse web_search_tool_result content blocks to extract cited sources.
        Returns: [{"title": str, "url": str, "snippet": str}]
        """
        sources = []
        for block in content_blocks:
            block_type = getattr(block, "type", "")
            if block_type == "web_search_tool_result":
                for result in getattr(block, "content", []):
                    if getattr(result, "type", "") == "web_search_result":
                        sources.append({
                            "title":   getattr(result, "title", ""),
                            "url":     getattr(result, "url", ""),
                            "snippet": getattr(result, "encrypted_content", "")[:500],
                        })
        return sources

    async def generate_document_with_skill(
        self,
        skill_id: str,
        prompt: str,
        context_data: str = None,
        task_context: dict = None,
        existing_container_id: str = None,
    ) -> dict:
        """
        Generate a formatted document using Anthropic Agent Skills.
        Handles the pause_turn continuation loop automatically.

        Args:
            skill_id:              "pptx" | "xlsx" | "pdf" | "docx"
            prompt:                Document generation instruction
            context_data:          Source data / content to base document on
            task_context:          Agent task dict for system prompt
            existing_container_id: Resume an existing container (multi-turn)

        Returns:
            {
              success:      bool,
              file_ids:     list[str],     # Anthropic Files API IDs
              container_id: str,           # For potential follow-up calls
              text:         str,           # Any text explanation in response
              usage:        dict,
              error:        str | None,
            }

        Important: file_ids must be downloaded via Files API.
        This method does NOT download files — call artifact_manager.download_from_anthropic()
        """
        if skill_id not in SKILL_CONFIGS:
            raise ValueError(f"Unknown skill_id: {skill_id}. Valid: {list(SKILL_CONFIGS.keys())}")

        # Build full prompt with context
        user_content = prompt
        if context_data:
            user_content += f"\n\n---\nSource data / context:\n{context_data}"

        messages = [{"role": "user", "content": user_content}]
        system = self._build_system_prompt(task_context) if task_context else None

        # Container setup — resume or start fresh
        container = {"skills": [SKILL_CONFIGS[skill_id]]}
        if existing_container_id:
            container["id"] = existing_container_id

        all_file_ids = []
        total_input_tokens = 0
        total_output_tokens = 0
        final_text = ""
        container_id = existing_container_id
        max_pause_turns = 10
        pause_count = 0

        # pause_turn loop — Skills may need multiple turns to complete generation
        while True:
            result = await self.claude.chat_with_server_tools(
                messages=messages,
                server_tools=[CODE_EXECUTION_TOOL],  # Required for Skills
                betas=SKILLS_BETAS,
                container=container,
                system=system,
            )

            # Accumulate results
            all_file_ids.extend(result["file_ids"])
            final_text = result["text"] or final_text
            container_id = result["container_id"] or container_id
            total_input_tokens  += result["usage"]["input_tokens"]
            total_output_tokens += result["usage"]["output_tokens"]

            # Update container to reuse on next loop
            if container_id:
                container = {
                    "id":     container_id,
                    "skills": [SKILL_CONFIGS[skill_id]],
                }

            # Check stop reason
            if result["stop_reason"] == "end_turn":
                break

            if result["stop_reason"] == "pause_turn":
                pause_count += 1
                if pause_count >= max_pause_turns:
                    logger.warning(f"Skill {skill_id} hit max pause_turns ({max_pause_turns})")
                    break
                # Append assistant response and send empty continue
                messages.append({"role": "assistant", "content": result["content"]})
                messages.append({"role": "user",      "content": []})
                continue

            # Any other stop reason — exit loop
            break

        # Track usage
        asyncio.create_task(self._track_usage_extended(
            model_name="claude-sonnet-4-6",
            department=(task_context or {}).get("department", "unknown"),
            user_id=(task_context or {}).get("user_id"),
            agent_id=(task_context or {}).get("agent_id"),
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            server_tools_used=["code_execution", f"skill:{skill_id}"],
            betas_used=SKILLS_BETAS,
            skill_id=skill_id,
        ))

        return {
            "success":      len(all_file_ids) > 0,
            "file_ids":     all_file_ids,
            "container_id": container_id,
            "text":         final_text,
            "usage": {
                "input_tokens":  total_input_tokens,
                "output_tokens": total_output_tokens,
            },
            "error": None if all_file_ids else "No file produced by Skill",
        }

    async def chat_with_memory(
        self,
        messages: list,
        memory_scope: str,
        client_tools: list = None,
        system: str = None,
    ) -> dict:
        """
        Chat with persistent memory tool enabled.
        Memory is scoped per entity so users and agents have separate memory spaces.

        memory_scope values:
          "user:{user_id}"        → User-level memory (personal preferences, history)
          "agent:{agent_id}"      → Agent-level memory (domain knowledge, learned patterns)
          "session:{session_id}"  → Session-scoped (cleared after session ends)

        The memory tool lets Claude read/write a persistent memory file directory.
        Memory files persist across conversations — Claude builds knowledge over time.

        Args:
            messages:      Conversation messages
            memory_scope:  Scoping key for this memory namespace
            client_tools:  Additional client-side tools to include
            system:        System prompt override

        Returns: standard extended response dict
        """
        server_tools = [MEMORY_TOOL]

        # Inject memory scope into system prompt
        memory_system = f"Your memory namespace for this session is: {memory_scope}. "
        memory_system += "Use memory to store and retrieve relevant information that should "
        memory_system += "persist across conversations for this entity.\n\n"
        if system:
            memory_system += system

        result = await self.claude.chat_with_server_tools(
            messages=messages,
            server_tools=server_tools,
            client_tools=client_tools,
            system=memory_system,
        )

        return result

    async def _track_usage_extended(
        self,
        model_name: str,
        department: str,
        user_id: str = None,
        agent_id: str = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        server_tools_used: list = None,
        betas_used: list = None,
        skill_id: str = None,
        cost_usd: float = None,
    ) -> None:
        """
        Extended token + cost tracking including Skills and server tool usage.
        Falls back to original _track_usage() signature if new columns don't exist yet.
        Non-fatal — failures are logged but do not affect the response.
        """
        import json as _json

        # Estimate cost if not provided (rough estimates, update as Anthropic pricing changes)
        if cost_usd is None:
            INPUT_COST_PER_1K  = 0.003   # claude-sonnet-4-6 input
            OUTPUT_COST_PER_1K = 0.015   # claude-sonnet-4-6 output
            cost_usd = (
                (input_tokens  / 1000 * INPUT_COST_PER_1K) +
                (output_tokens / 1000 * OUTPUT_COST_PER_1K)
            )

        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text

            sql = """
                INSERT INTO llm_usage (
                    model, department, user_id, agent_id,
                    input_tokens, output_tokens, cost_usd,
                    server_tools_used, betas_used, skill_id
                )
                VALUES (
                    :model, :department, :user_id, :agent_id,
                    :input_tokens, :output_tokens, :cost_usd,
                    :server_tools_used, :betas_used, :skill_id
                )
            """
            async with AsyncSessionLocal() as session:
                await session.execute(text(sql), {
                    "model":             model_name,
                    "department":        department,
                    "user_id":           user_id,
                    "agent_id":          agent_id,
                    "input_tokens":      input_tokens,
                    "output_tokens":     output_tokens,
                    "cost_usd":          cost_usd,
                    "server_tools_used": _json.dumps(server_tools_used or []),
                    "betas_used":        _json.dumps(betas_used or []),
                    "skill_id":          skill_id,
                })
                await session.commit()
        except Exception:
            # Fallback to original schema if new columns not yet migrated
            await self._track_usage(
                model_name, department, user_id or "system",
                input_tokens, output_tokens,
            )
