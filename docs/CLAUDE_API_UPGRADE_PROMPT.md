# Claude Code CLI Prompt — Anthropic API Full Audit & Upgrade
## Mezzofy AI Assistant · Integrate Native Claude API Capabilities

---

## CONTEXT — What We Are Upgrading

The current Mezzofy AI Assistant uses Claude API in a basic way:
- Simple tool calling loop in `llm_manager.py`
- Custom Python libraries for document generation (pdf_ops, pptx_ops, docx_ops)
- Custom web scraping via Playwright (browser_ops, scraping_ops)
- No use of Anthropic's server-side tools (web_search, web_fetch)
- No use of Agent Skills (pptx, xlsx, pdf, docx)
- No use of the Files API for artifact management
- No use of the Memory tool for persistent agent/user state

This prompt upgrades the entire LLM layer, document pipeline, web research pipeline,
and artifact management to leverage the full Anthropic API native capability set.

**All changes are additive. No existing working code is deleted.**
**No FastAPI, Celery, or Celery Beat restarts during this session.**

---

## PHASE 0 — Codebase Audit (Run First, Report Before Proceeding)

```
Audit targets — read each file and report findings:

[ ] server/app/llm/anthropic_client.py
    → Current SDK version (check requirements.txt: anthropic>=?)
    → Does it use client.beta.messages.create() anywhere?
    → Does it handle pause_turn stop_reason?
    → Does it pass betas=[] or container={} params?
    → Does it handle server_tool_use content blocks?

[ ] server/app/llm/llm_manager.py
    → Current tool calling loop structure
    → Does it distinguish server-side vs client-side tools?
    → Does it handle web_search / web_fetch tool result blocks?
    → Does it track skill-related beta usage separately in llm_usage?

[ ] server/tools/document/
    → List all files — confirm pdf_ops.py, pptx_ops.py, docx_ops.py, csv_ops.py exist
    → Does anthropic_skills.py exist already?

[ ] server/tools/web/browser_ops.py + scraping_ops.py
    → What tools are registered (open_page, scrape_url, search_web, etc.)?
    → Is there already a web_search or web_fetch wrapper?

[ ] server/app/context/artifact_manager.py
    → Current store() method — does it handle Anthropic file_id?
    → Does artifacts table have anthropic_file_id column?

[ ] server/app/context/  (or elsewhere)
    → Does a memory_manager.py exist?
    → Is there any use of type:"memory" tool in API calls?

[ ] server/alembic/versions/ or server/scripts/migrate.py
    → List existing tables — confirm: artifacts, llm_usage, users, agents,
      agent_task_log tables exist
    → Does artifacts table have: anthropic_file_id, skill_id, generation_source columns?
    → Does llm_usage have: betas_used, skill_id, cost_usd columns?

[ ] server/config/config.yaml
    → Confirm anthropic_skills section exists or is absent
    → Confirm model string — should be claude-sonnet-4-6

[ ] requirements.txt
    → Current anthropic SDK version
    → httpx version

Report all findings as a numbered list. Flag any conflicts before proceeding.
```

---

## PHASE 1 — Update anthropic_client.py

### File: `server/app/llm/anthropic_client.py`

**DO NOT rewrite the class. Add new methods and update existing ones additively.**

#### 1.1 Upgrade SDK Version Check

Ensure `requirements.txt` has:
```
anthropic>=0.52.0
httpx>=0.27.0
```
Run `pip show anthropic` to get current version. If below 0.52.0:
`pip install --upgrade anthropic --break-system-packages`

#### 1.2 Add: Server-Side Tools Support

Add the following new method to `AnthropicClient`. Do NOT modify the existing `chat()` method:

```python
async def chat_with_server_tools(
    self,
    messages: list,
    server_tools: list = None,
    client_tools: list = None,
    betas: list = None,
    container: dict = None,
    system: str = None,
    max_tokens: int = 8192,
) -> dict:
    """
    Extended chat method supporting Anthropic server-side tools and Agent Skills.

    Server tools (Anthropic executes — no local implementation needed):
      - web_search:      {"type": "web_search_20260209", "name": "web_search"}
      - web_fetch:       {"type": "web_fetch_20250124",  "name": "web_fetch"}
      - code_execution:  {"type": "code_execution_20250825", "name": "code_execution"}
      - memory:          {"type": "memory", "name": "memory"}

    Agent Skills (via container + betas):
      betas = ["code-execution-2025-08-25", "skills-2025-10-02"]
      container = {"skills": [{"type": "anthropic", "skill_id": "pptx", "version": "latest"}]}

    Returns:
      {
        content: [...],          # full content blocks
        stop_reason: str,        # "end_turn" | "pause_turn" | "tool_use"
        container_id: str|None,  # for continuing Skills sessions
        text: str,               # extracted text blocks joined
        file_ids: list[str],     # file_ids from Skills output
        tool_uses: list[dict],   # server_tool_use blocks
        usage: dict,             # input/output tokens
      }
    """
    # Build tools list — server tools + client tools combined
    tools = []
    if server_tools:
        tools.extend(server_tools)
    if client_tools:
        tools.extend(client_tools)

    # Build request params
    params = {
        "model":      self.model,
        "max_tokens": max_tokens,
        "messages":   messages,
        "tools":      tools if tools else None,
    }
    if system:
        params["system"] = system
    if container:
        params["container"] = container

    # Use beta client if betas specified
    if betas:
        response = await self.client.beta.messages.create(
            **{k: v for k, v in params.items() if v is not None},
            betas=betas,
        )
    else:
        response = await self.client.messages.create(
            **{k: v for k, v in params.items() if v is not None},
        )

    return self._parse_extended_response(response)

def _parse_extended_response(self, response) -> dict:
    """
    Parse response handling all content block types:
      - text blocks
      - tool_use blocks (client tools Claude wants to call)
      - server_tool_use blocks (web_search, web_fetch executing)
      - web_search_tool_result blocks
      - code_execution_result blocks
      - document/file blocks (from Skills)
    """
    text_parts = []
    file_ids = []
    tool_uses = []
    server_tool_uses = []
    container_id = getattr(response, "container", None)
    if container_id:
        container_id = getattr(container_id, "id", None)

    for block in response.content:
        block_type = getattr(block, "type", "")

        if block_type == "text":
            text_parts.append(block.text)

        elif block_type == "tool_use":
            # Client tool call — we need to execute locally
            tool_uses.append({
                "id":    block.id,
                "name":  block.name,
                "input": block.input,
            })

        elif block_type == "server_tool_use":
            # Anthropic is executing this — just track it
            server_tool_uses.append({
                "id":   block.id,
                "name": block.name,
                "input": getattr(block, "input", {}),
            })

        elif block_type in ("document", "file"):
            # File produced by a Skill
            fid = getattr(block, "file_id", None)
            if fid:
                file_ids.append(fid)

        # web_search_tool_result and code_execution_result are
        # handled server-side — they appear in content but
        # we don't need to act on them locally

    return {
        "content":       response.content,
        "stop_reason":   response.stop_reason,
        "container_id":  container_id,
        "text":          "\n".join(text_parts),
        "file_ids":      file_ids,
        "tool_uses":     tool_uses,
        "server_tool_uses": server_tool_uses,
        "usage": {
            "input_tokens":  response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
```

---

## PHASE 2 — Upgrade llm_manager.py

### File: `server/app/llm/llm_manager.py`

**Add the following new methods. Do NOT modify `execute_with_tools()`.**

#### 2.1 Add: Server Tool Definitions Registry

```python
# Add as module-level constants — these are the Anthropic server-side tool definitions

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
```

#### 2.2 Add: Web Research Method (replaces browser_ops + scraping_ops for research tasks)

```python
async def research_with_web_tools(
    self,
    query: str,
    task_context: dict,
    fetch_urls: list[str] = None,
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
        query:             Research query or instruction
        task_context:      Agent task dict (for system prompt + user context)
        fetch_urls:        Specific URLs to fetch (optional, in addition to search)
        use_code_execution: Enable code execution for data processing

    Returns:
        {
          text: str,           # Research findings
          sources: list[dict], # [{title, url, snippet}] from web_search results
          usage: dict,
        }

    Flow:
      1. Build server_tools list (always web_search, optionally web_fetch + code_exec)
      2. Build user message (query + any specific URLs to fetch)
      3. Call claude.chat_with_server_tools() — Anthropic handles the search loop
      4. Parse web_search_tool_result blocks to extract sources
      5. Return structured findings
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
    await self._track_usage_extended(
        model_name="claude-sonnet-4-6",
        department=task_context.get("department", "unknown"),
        user_id=task_context.get("user_id"),
        agent_id=task_context.get("agent_id"),
        input_tokens=result["usage"]["input_tokens"],
        output_tokens=result["usage"]["output_tokens"],
        server_tools_used=["web_search", "web_fetch"],
        betas_used=[],
    )

    return {
        "text":    result["text"],
        "sources": sources,
        "usage":   result["usage"],
    }

def _extract_web_sources(self, content_blocks: list) -> list[dict]:
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
```

#### 2.3 Add: Document Generation via Agent Skills

```python
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
    await self._track_usage_extended(
        model_name="claude-sonnet-4-6",
        department=(task_context or {}).get("department", "unknown"),
        user_id=(task_context or {}).get("user_id"),
        agent_id=(task_context or {}).get("agent_id"),
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        server_tools_used=["code_execution", f"skill:{skill_id}"],
        betas_used=SKILLS_BETAS,
        skill_id=skill_id,
    )

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
```

#### 2.4 Add: Memory Tool Support (User + Agent Level)

```python
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
    # Memory tool definition — GA, no beta needed
    memory_tool_def = {
        "type": "memory",
        "name": "memory",
    }

    server_tools = [memory_tool_def]
    tools = server_tools + (client_tools or [])

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
```

#### 2.5 Update: `_track_usage_extended()`

Replace the existing `_track_usage()` with this extended version. The new columns are added via migration in Phase 5:

```python
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
):
    """
    Extended token + cost tracking including Skills and server tool usage.
    Falls back to original _track_usage() signature if new columns don't exist yet.
    """
    # Estimate cost if not provided (rough estimates, update as Anthropic pricing changes)
    if cost_usd is None:
        INPUT_COST_PER_1K  = 0.003   # claude-sonnet-4-6 input
        OUTPUT_COST_PER_1K = 0.015   # claude-sonnet-4-6 output
        cost_usd = (
            (input_tokens  / 1000 * INPUT_COST_PER_1K) +
            (output_tokens / 1000 * OUTPUT_COST_PER_1K)
        )

    try:
        await self.db.execute("""
            INSERT INTO llm_usage (
                model, department, user_id, agent_id,
                input_tokens, output_tokens, cost_usd,
                server_tools_used, betas_used, skill_id,
                timestamp
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
        """,
            model_name, department, user_id, agent_id,
            input_tokens, output_tokens, cost_usd,
            json.dumps(server_tools_used or []),
            json.dumps(betas_used or []),
            skill_id,
        )
    except Exception:
        # Fallback to original schema if new columns not yet migrated
        await self._track_usage(model_name, department, user_id, input_tokens, output_tokens)
```

---

## PHASE 3 — Upgrade artifact_manager.py

### File: `server/app/context/artifact_manager.py`

**Add these new methods. Do NOT modify `store()`, `get_artifact()`, or `list_artifacts()`.**

```python
import httpx
import json
from pathlib import Path

FILES_API_BASE = "https://api.anthropic.com/v1/files"
FILES_API_BETA = "files-api-2025-04-14"

async def download_from_anthropic(
    self,
    file_id: str,
    user_id: str,
    session_id: str,
    skill_id: str,
    suggested_name: str = None,
    agent_id: str = None,
) -> dict:
    """
    Download a file from Anthropic Files API and store it in our artifact system.

    This is called immediately after generate_document_with_skill() returns file_ids.
    It bridges the Anthropic Files API → our local artifact storage → artifacts DB table.

    Args:
        file_id:        Anthropic Files API ID (from Skills response)
        user_id:        Owner user_id (for RBAC)
        session_id:     Associated conversation session
        skill_id:       "pptx" | "xlsx" | "pdf" | "docx" (for file extension + type)
        suggested_name: Base filename without extension (auto-generated if None)
        agent_id:       Which agent generated this file (for audit)

    Returns:
        {
          artifact_id:  str,   # Our local artifacts table UUID
          file_path:    str,   # Local EBS/S3 path
          download_url: str,   # Our API download URL
          size_bytes:   int,
        }
    """
    # Determine extension + type from skill_id
    SKILL_EXTENSIONS = {
        "pptx": (".pptx", "pptx", "presentations"),
        "xlsx": (".xlsx", "xlsx", "exports"),
        "pdf":  (".pdf",  "pdf",  "documents"),
        "docx": (".docx", "docx", "documents"),
    }
    ext, file_type, subdir = SKILL_EXTENSIONS.get(skill_id, (".bin", "file", "uploads"))

    # Auto-generate filename if not provided
    if not suggested_name:
        import time
        suggested_name = f"{skill_id}_{int(time.time())}"
    filename = suggested_name + ext

    # Download from Anthropic Files API
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{FILES_API_BASE}/{file_id}/content",
            headers={
                "x-api-key":        self.config["llm"]["claude"]["api_key"],
                "anthropic-version": "2023-06-01",
                "anthropic-beta":   FILES_API_BETA,
            },
        )
        response.raise_for_status()
        file_bytes = response.content

    # Save to local artifact storage (EBS or S3)
    dest_dir  = Path(self.storage_path) / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    dest_path.write_bytes(file_bytes)

    # Record in artifacts table (with new anthropic_file_id column)
    artifact_id = await self._store_artifact_record(
        user_id=user_id,
        session_id=session_id,
        file_path=str(dest_path),
        file_type=file_type,
        name=filename,
        size_bytes=len(file_bytes),
        anthropic_file_id=file_id,
        skill_id=skill_id,
        generation_source="anthropic_skill",
        agent_id=agent_id,
    )

    # Optionally delete from Anthropic Files API after download
    # (to avoid Anthropic storage charges — files are now on our EBS)
    await self._delete_anthropic_file(file_id)

    return {
        "artifact_id":  artifact_id,
        "file_path":    str(dest_path),
        "download_url": f"/files/{artifact_id}",
        "size_bytes":   len(file_bytes),
    }

async def _delete_anthropic_file(self, file_id: str):
    """Delete file from Anthropic Files API after we've downloaded it."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.delete(
                f"{FILES_API_BASE}/{file_id}",
                headers={
                    "x-api-key":        self.config["llm"]["claude"]["api_key"],
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta":   FILES_API_BETA,
                },
            )
    except Exception as e:
        # Non-fatal — log but don't raise
        logger.warning(f"Failed to delete Anthropic file {file_id}: {e}")

async def upload_to_anthropic(
    self,
    file_path: str,
    media_type: str = None,
) -> str:
    """
    Upload a local file to Anthropic Files API for use in API calls.
    Returns the Anthropic file_id.

    Use case: uploading user-provided PDFs/DOCX for Claude to read and analyse,
    without re-uploading on every API call (Files API caches them).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Auto-detect media type if not provided
    if media_type is None:
        MEDIA_TYPES = {
            ".pdf":  "application/pdf",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".txt":  "text/plain",
            ".csv":  "text/csv",
        }
        media_type = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")

    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(path, "rb") as f:
            response = await client.post(
                FILES_API_BASE,
                headers={
                    "x-api-key":        self.config["llm"]["claude"]["api_key"],
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta":   FILES_API_BETA,
                },
                files={"file": (path.name, f, media_type)},
            )
        response.raise_for_status()
        return response.json()["id"]
```

---

## PHASE 4 — Upgrade Agent Base Class: Wire New LLM Methods

### File: `server/agents/base_agent.py`

**Add these new methods. Do NOT modify `execute()` or `_load_skill()`.**

```python
async def research_web(
    self,
    query: str,
    fetch_urls: list[str] = None,
    use_code_execution: bool = False,
) -> dict:
    """
    Perform web research using Anthropic's native web_search + web_fetch tools.
    PREFERRED over browser_ops.search_web() for general research tasks.
    Returns: { text: str, sources: list[{title, url, snippet}] }
    """
    return await self.llm.research_with_web_tools(
        query=query,
        task_context=self._build_task_context(),
        fetch_urls=fetch_urls,
        use_code_execution=use_code_execution,
    )

async def generate_document(
    self,
    skill_id: str,
    prompt: str,
    context_data: str = None,
    suggested_filename: str = None,
    task: dict = None,
    deliver_via: dict = None,
) -> dict:
    """
    Generate a formatted document using Anthropic Agent Skills,
    then download via Files API and store in artifact system.

    This is the SINGLE entry point all agents use for document generation.
    It replaces direct calls to: pdf_ops, pptx_ops, docx_ops.

    Args:
        skill_id:           "pptx" | "xlsx" | "pdf" | "docx"
        prompt:             Document generation instruction with full detail
        context_data:       Structured data / content (DB results, research findings, etc.)
        suggested_filename: Base filename (no extension)
        task:               Parent task dict (for user_id, session_id, agent_id)
        deliver_via:        Optional delivery {
                              "teams_channel": "sales",
                              "email": ["user@mezzofy.com"],
                              "push_user_id": "user_123"
                            }

    Returns:
        {
          success:      bool,
          artifact_id:  str,
          file_path:    str,
          download_url: str,
          size_bytes:   int,
          delivered_to: list[str],
          error:        str | None,
        }

    Full pipeline:
      1. llm_manager.generate_document_with_skill()
         → calls Claude API with Skills beta + pause_turn loop
         → returns file_ids (Anthropic Files API)
      2. artifact_manager.download_from_anthropic()
         → downloads each file_id
         → stores in /data/artifacts/{type}/
         → records in artifacts DB table
         → deletes from Anthropic Files API (saves their storage cost)
      3. Optional: deliver via Teams + email if deliver_via is set
      4. Returns artifact info + delivery confirmation
    """
    task = task or {}
    user_id    = task.get("user_id") or "system"
    session_id = task.get("session_id") or "auto"
    agent_id   = self.agent_record.get("id") if hasattr(self, "agent_record") else None

    # Step 1: Generate via Anthropic Skill
    skill_result = await self.llm.generate_document_with_skill(
        skill_id=skill_id,
        prompt=prompt,
        context_data=context_data,
        task_context=self._build_task_context(task),
    )

    if not skill_result["success"]:
        # Fallback to legacy library tool
        logger.warning(
            f"Anthropic Skill {skill_id} failed: {skill_result['error']}. "
            f"Falling back to legacy {skill_id}_ops."
        )
        return await self._generate_document_fallback(skill_id, prompt, context_data, task)

    # Step 2: Download each file and store in artifacts
    artifacts = []
    for i, file_id in enumerate(skill_result["file_ids"]):
        name = suggested_filename or f"{self.agent_record.get('department','agent')}_{skill_id}"
        if len(skill_result["file_ids"]) > 1:
            name += f"_{i+1}"

        artifact = await self.artifact_manager.download_from_anthropic(
            file_id=file_id,
            user_id=user_id,
            session_id=session_id,
            skill_id=skill_id,
            suggested_name=name,
            agent_id=agent_id,
        )
        artifacts.append(artifact)

    if not artifacts:
        return {"success": False, "error": "File download failed after Skill generation"}

    primary = artifacts[0]

    # Step 3: Optional delivery
    delivered_to = []
    if deliver_via:
        delivered_to = await self._deliver_artifact(primary, deliver_via, task)

    return {
        "success":      True,
        "artifact_id":  primary["artifact_id"],
        "file_path":    primary["file_path"],
        "download_url": primary["download_url"],
        "size_bytes":   primary["size_bytes"],
        "delivered_to": delivered_to,
        "error":        None,
    }

async def _deliver_artifact(self, artifact: dict, deliver_via: dict, task: dict) -> list[str]:
    """
    Deliver a generated artifact via configured channels.
    Called automatically from generate_document() when deliver_via is provided.
    Also callable directly for manual delivery of existing artifacts.

    Channels:
      teams_channel: post file to MS Teams channel (attach the file)
      email:         send via Outlook to list of recipients
      push_user_id:  mobile push notification to user
    """
    delivered_to = []
    file_path = artifact["file_path"]
    filename  = Path(file_path).name

    if deliver_via.get("teams_channel"):
        channel = deliver_via["teams_channel"]
        await self.tools["teams_post_message"].execute(
            channel=channel,
            text=f"📎 New document ready: **{filename}**",
            attachments=[file_path],
        )
        delivered_to.append(f"teams:{channel}")

    if deliver_via.get("email"):
        for recipient in deliver_via["email"]:
            await self.tools["outlook_send_email"].execute(
                to=recipient,
                subject=f"[Mezzofy AI] {filename}",
                body=f"Your requested document is attached: {filename}",
                attachments=[file_path],
            )
            delivered_to.append(f"email:{recipient}")

    if deliver_via.get("push_user_id"):
        await self.tools["send_push"].execute(
            user_id=deliver_via["push_user_id"],
            title="Document Ready",
            body=f"{filename} has been generated and is ready to download.",
        )
        delivered_to.append(f"push:{deliver_via['push_user_id']}")

    return delivered_to

async def read_document_via_api(
    self,
    file_path: str,
    question: str = None,
) -> str:
    """
    Upload a local file to Anthropic Files API for analysis.
    More efficient than re-uploading on every API call for large files.

    Use case:
      - User uploads a contract PDF → analyse with Leo (Legal Agent)
      - User uploads a spreadsheet → analyse financial data
      - User uploads a presentation → extract + summarise content

    Returns: extracted content / analysis as text
    """
    # Upload to Anthropic Files API (cached for 1 hour by default)
    file_id = await self.artifact_manager.upload_to_anthropic(file_path)

    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        document_block = {
            "type":   "document",
            "source": {"type": "file", "file_id": file_id},
        }
    else:
        document_block = {
            "type": "text",
            "text": f"[File uploaded: {Path(file_path).name}, file_id: {file_id}]",
        }

    prompt_content = question or "Please analyse this document and provide a comprehensive summary."
    messages = [
        {
            "role":    "user",
            "content": [
                document_block,
                {"type": "text", "text": prompt_content},
            ],
        }
    ]

    result = await self.llm.claude.chat_with_server_tools(
        messages=messages,
        system=self._build_task_context_system(),
    )
    return result["text"]

def _build_task_context(self, task: dict = None) -> dict:
    """Build task context dict for LLM method calls."""
    task = task or {}
    agent_record = getattr(self, "agent_record", {})
    return {
        "department": agent_record.get("department", task.get("department", "general")),
        "user_id":    task.get("user_id"),
        "agent_id":   agent_record.get("id"),
        "role":       task.get("role", "assistant"),
        "source":     task.get("source", "mobile"),
    }
```

---

## PHASE 5 — Update Each Specialist Agent

For each agent, update the document generation calls to use the new `generate_document()` method from BaseAgent. **Do NOT modify any other logic in these agents.**

### Target: Replace direct tool calls like this:
```python
# OLD — direct tool call
result = await self.tools["pdf_generator"].execute(content=report_text, template="financial")

# NEW — Anthropic Skill via base class
result = await self.generate_document(
    skill_id="pdf",
    prompt="Generate a professional financial statement PDF...",
    context_data=financial_data_json,
    suggested_filename="financial_statement_q1_2026",
    task=task,
    deliver_via=task.get("deliver_to"),   # honours existing deliver_to field
)
```

### Changes per agent:

**`finance_agent.py`**
- `pdf_generator` calls → `generate_document(skill_id="pdf", ...)`
- Any Excel/CSV financial export → `generate_document(skill_id="xlsx", ...)`
- Web research for market data → `research_web(query=..., fetch_urls=[...])`

**`sales_agent.py`**
- `pptx_generator` (pitch decks) → `generate_document(skill_id="pptx", ...)`
- Proposal PDFs → `generate_document(skill_id="pdf", ...)`
- Company research → `research_web(query=f"Research {company_name}...")`
- web_scraper for company profiles → `research_web(query=..., fetch_urls=[url])`

**`marketing_agent.py`**
- Playbook PDFs → `generate_document(skill_id="pdf", ...)`
- Content DOCX → `generate_document(skill_id="docx", ...)`
- Competitor research → `research_web(query=..., use_code_execution=True)`

**`legal_agent.py`** (Leo)
- Contract DOCX → `generate_document(skill_id="docx", ...)`
- Risk report PDF → `generate_document(skill_id="pdf", ...)`
- Document review → `read_document_via_api(file_path=..., question=...)`
- Jurisdiction research → `research_web(query=..., fetch_urls=[...])`

**`management_agent.py`**
- KPI report PDF → `generate_document(skill_id="pdf", ...)`
- Financial dashboards → `generate_document(skill_id="xlsx", ...)`

**`hr_agent.py`**
- HR report PDF → `generate_document(skill_id="pdf", ...)`
- Headcount spreadsheet → `generate_document(skill_id="xlsx", ...)`

**`research_agent.py`** (Rex)
- ALL web research → `research_web()` (this IS Rex's primary tool)
- Research brief PDF → `generate_document(skill_id="pdf", ...)`

---

## PHASE 6 — Add Memory Manager

### New file: `server/app/context/memory_manager.py`

```python
"""
Memory Manager — User-Level and Agent-Level Persistent Memory
Uses Anthropic's native Memory tool (type: "memory") to persist
knowledge across conversations for both users and agents.

Memory is scoped at two levels:
  1. USER MEMORY  — personal preferences, workflow habits, project context,
                    past decisions. Tied to user_id.
  2. AGENT MEMORY — domain knowledge accumulated over time, successful patterns,
                    common corrections, client preferences. Tied to agent_id.

Neither level can read the other's memory.
"""

class MemoryManager:
    """
    Manages memory namespacing for users and agents.
    Injects the memory tool into API calls with appropriate scope.
    Provides audit trail for memory operations.
    """

    def get_user_memory_scope(self, user_id: str) -> str:
        """Returns scoped memory namespace for a user."""
        return f"user:{user_id}"

    def get_agent_memory_scope(self, agent_id: str) -> str:
        """Returns scoped memory namespace for an agent."""
        return f"agent:{agent_id}"

    def build_memory_system_prompt(self, scope: str, base_system: str = "") -> str:
        """
        Injects memory scope instruction into the system prompt.
        Claude uses this to know which memory namespace to read/write.
        """
        entity_type = scope.split(":")[0]   # "user" or "agent"
        entity_id   = scope.split(":")[1]

        if entity_type == "user":
            memory_instruction = (
                f"You have persistent memory for user {entity_id}. "
                f"Your memory namespace is '{scope}'. "
                f"Use memory to remember: user preferences, ongoing projects, "
                f"past decisions, communication style, and any context the user "
                f"has shared that will be useful in future conversations."
            )
        else:
            memory_instruction = (
                f"You are {entity_id} and have persistent agent memory. "
                f"Your memory namespace is '{scope}'. "
                f"Use memory to remember: successful workflow patterns, "
                f"common corrections to avoid, domain-specific insights learned "
                f"from tasks, and organisational knowledge that improves your work."
            )

        return f"{memory_instruction}\n\n{base_system}".strip()

    def get_memory_tool_definition(self) -> dict:
        """Returns the Anthropic memory tool definition for API calls."""
        return {"type": "memory", "name": "memory"}

    async def log_memory_operation(
        self,
        db,
        scope: str,
        operation: str,
        summary: str,
    ):
        """
        Audit log entry for memory read/write operations.
        operation: "read" | "write" | "update" | "delete"
        """
        entity_type, entity_id = scope.split(":", 1)
        await db.execute("""
            INSERT INTO audit_log (
                action, entity_type, entity_id, details, timestamp
            ) VALUES ($1, $2, $3, $4, NOW())
        """,
            f"memory_{operation}",
            entity_type,
            entity_id,
            summary,
        )
```

Register `MemoryManager` in `main.py` startup alongside `AgentRegistry`.

---

## PHASE 7 — Update config.yaml

Add the following new sections to `server/config/config.yaml`.
**Append only — do not modify existing sections:**

```yaml
# ── Anthropic Native API Capabilities ───────────────────────────────────────
anthropic_native:
  # Server-side tools (GA — no beta header)
  web_search:
    enabled: true
    # enable_organization: must be toggled ON in Claude Console by admin
    # https://console.anthropic.com → Settings → Capabilities → Web search
    dynamic_filtering: true    # uses code_execution to pre-filter results

  web_fetch:
    enabled: true
    # Free to use, no extra cost beyond tokens

  code_execution:
    enabled: true
    # Free when used alongside web_search or web_fetch
    # Standalone: $0.05 per session-hour

  memory:
    enabled: true
    user_memory: true     # per-user persistent memory
    agent_memory: true    # per-agent persistent memory

  # Agent Skills (beta: skills-2025-10-02)
  skills:
    enabled: true
    # Requires code_execution to also be enabled
    fallback_to_legacy_libs: true   # use pdf_ops/pptx_ops if Skills API fails
    max_pause_turns: 10
    auto_delete_from_anthropic_after_download: true
    supported:
      - skill_id: "pptx"
        primary_agents: ["agent_sales", "agent_marketing", "agent_management"]
      - skill_id: "xlsx"
        primary_agents: ["agent_finance", "agent_management", "agent_hr"]
      - skill_id: "pdf"
        primary_agents: ["agent_finance", "agent_legal", "agent_hr", "agent_management"]
      - skill_id: "docx"
        primary_agents: ["agent_legal", "agent_marketing", "agent_hr"]

  # Files API (beta: files-api-2025-04-14)
  files_api:
    enabled: true
    max_file_size_mb: 100
    auto_delete_after_download: true   # delete from Anthropic after saving locally
    supported_upload_types:
      - "application/pdf"
      - "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      - "application/vnd.openxmlformats-officedocument.presentationml.presentation"
      - "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      - "image/jpeg"
      - "image/png"
      - "text/plain"
      - "text/csv"

# ── Updated LLM config (model string update) ────────────────────────────────
# Update existing llm.claude.model string:
# OLD: claude-sonnet-4-5-20250929
# NEW: claude-sonnet-4-6
#
# Also add:
# llm.claude.max_tokens: 8192  (increased from 4096 for Skills generation)
```

---

## PHASE 8 — DB Migration: New Columns

### New migration: `server/alembic/versions/XXXX_anthropic_api_upgrade.py`

```sql
-- artifacts table: track Anthropic file origin
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS anthropic_file_id   VARCHAR(64);
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS skill_id            VARCHAR(16);
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS generation_source   VARCHAR(32)
    DEFAULT 'legacy_lib';
    -- "anthropic_skill" | "legacy_lib" | "user_upload"

-- llm_usage table: track native API features
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS agent_id            VARCHAR(32);
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS cost_usd            NUMERIC(10,6) DEFAULT 0;
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS server_tools_used   JSONB DEFAULT '[]';
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS betas_used          JSONB DEFAULT '[]';
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS skill_id            VARCHAR(16);

-- memory_log table: audit trail for memory tool operations
CREATE TABLE IF NOT EXISTS memory_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope           VARCHAR(128) NOT NULL,  -- "user:{id}" or "agent:{id}"
    operation       VARCHAR(16) NOT NULL,   -- "read" | "write" | "update" | "delete"
    summary         TEXT,
    session_id      VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memory_log_scope ON memory_log(scope);

-- Update model string in any existing config records if stored in DB
-- (No action needed if model is only in config.yaml)
```

Run: `alembic upgrade head`

---

## PHASE 9 — Update tools/document Directory

### Rename + document legacy tools as fallbacks:

```python
# At the top of pdf_ops.py, pptx_ops.py, docx_ops.py — add this docstring:

"""
FALLBACK ONLY — This module is used when Anthropic Agent Skills API is unavailable.

Primary document generation path:
  → BaseAgent.generate_document(skill_id="pdf|pptx|xlsx|docx", ...)
  → llm_manager.generate_document_with_skill()
  → Anthropic Skills API (beta: skills-2025-10-02)
  → artifact_manager.download_from_anthropic()

This fallback is triggered automatically when:
  - Anthropic API returns an error
  - config.anthropic_native.skills.fallback_to_legacy_libs = true
  - The skill result["success"] is False

Do NOT call this module directly from agents — use BaseAgent.generate_document().
"""
```

### Keep `csv_ops.py` as PRIMARY — no change:
CSV export is pure data export (no formatting intelligence needed), so it stays as direct pandas/csv generation. Do not route CSV through Anthropic Skills.

---

## PHASE 10 — Tests

Create `server/tests/test_anthropic_api_upgrade.py`:

```python
# Tests to implement:

# 1. test_chat_with_server_tools_web_search
#    — Mock Anthropic beta client
#    — Assert web_search_20260209 tool included in request
#    — Assert web_search_tool_result blocks parsed into sources list

# 2. test_research_with_web_tools
#    — Mock Anthropic response with web_search results
#    — Assert return dict has text + sources
#    — Assert llm_usage row created with server_tools_used=["web_search","web_fetch"]

# 3. test_generate_document_with_skill_pptx
#    — Mock Skills API response with file_id
#    — Assert stop_reason=end_turn exits loop correctly
#    — Assert file_ids=[...] returned

# 4. test_generate_document_pause_turn_loop
#    — Mock first response: stop_reason=pause_turn
#    — Mock second response: stop_reason=end_turn, file_id present
#    — Assert loop ran exactly 2 times
#    — Assert final file_ids is populated

# 5. test_download_from_anthropic
#    — Mock httpx GET to Anthropic Files API
#    — Assert file saved to local artifact path
#    — Assert artifacts table row created with anthropic_file_id + skill_id columns
#    — Assert DELETE called on Anthropic Files API (auto_delete=true)

# 6. test_upload_to_anthropic
#    — Mock httpx POST to Anthropic Files API
#    — Assert returns file_id string

# 7. test_generate_document_fallback_on_failure
#    — Mock Skills API to return success=False
#    — Assert fallback (legacy pdf_ops) is called
#    — Assert no exception raised to caller

# 8. test_base_agent_generate_document_end_to_end
#    — Mock LLM manager generate_document_with_skill()
#    — Mock artifact_manager.download_from_anthropic()
#    — Assert final result has success=True, artifact_id, download_url

# 9. test_deliver_artifact_teams_and_email
#    — Mock teams_post_message and outlook_send_email tools
#    — Call _deliver_artifact() with both channels configured
#    — Assert delivered_to = ["teams:sales", "email:cfo@mezzofy.com"]

# 10. test_memory_scope_user_level
#     — MemoryManager.get_user_memory_scope("user_123") = "user:user_123"
#     — build_memory_system_prompt includes "user:user_123" in text

# 11. test_memory_scope_agent_level
#     — MemoryManager.get_agent_memory_scope("agent_sales") = "agent:agent_sales"
#     — Memory tool definition included in API call

# 12. test_llm_usage_extended_tracking
#     — After generate_document_with_skill() call
#     — Assert llm_usage row has skill_id, betas_used, cost_usd populated

# 13. test_read_document_via_api
#     — Mock upload_to_anthropic() → returns fake file_id
#     — Mock chat_with_server_tools() → returns analysis text
#     — Assert document block with file_id sent to API

# 14. test_web_search_replaces_browser_ops_for_research
#     — ResearchAgent.research_web("Find competitors")
#     — Assert research_with_web_tools() called (NOT browser_ops)
#     — Assert sources list returned alongside text
```

Run: `pytest server/tests/test_anthropic_api_upgrade.py -v`

---

## PHASE 11 — Update Documentation

### `LLM.md` — Add new section after existing Tool Calling Loop:

```markdown
## Anthropic Native API Capabilities

### Server-Side Tools (GA)

These tools are executed by Anthropic's servers — no local implementation needed.
Include them in the `tools` array of any API call:

| Tool | Type String | Purpose | Cost |
|------|-------------|---------|------|
| Web Search | `web_search_20260209` | Real-time web with citations | Per-search fee |
| Web Fetch | `web_fetch_20250124` | Full URL content retrieval | Token cost only |
| Code Execution | `code_execution_20250825` | Python sandbox | Free with web search |
| Memory | `memory` | Persistent memory files | Token cost only |

### Agent Skills (beta: skills-2025-10-02)

Invoked via `container.skills` alongside `code_execution` tool.
Returns `file_id` — download via Files API.

| Skill | skill_id | Purpose |
|-------|----------|---------|
| PowerPoint | `pptx` | Presentation decks |
| Excel | `xlsx` | Spreadsheets with formulas |
| PDF | `pdf` | Professional documents |
| Word | `docx` | Business documents, contracts |

### Files API (beta: files-api-2025-04-14)

`POST /v1/files` — upload files for multi-call reuse
`GET  /v1/files/{id}/content` — download generated files
`DELETE /v1/files/{id}` — clean up after download

### Two-Phase Document Generation Pipeline

1. Agent gathers data (DB, CRM, web research via native tools)
2. `BaseAgent.generate_document()` → Skills API generates file → file_id returned
3. `ArtifactManager.download_from_anthropic()` → saves locally → records in artifacts table
4. Optional: deliver via Teams + email per `deliver_via` config
```

---

## EXECUTION ORDER

```
Phase 0  → Audit — read all target files, report findings
Phase 1  → Update anthropic_client.py (add chat_with_server_tools)
Phase 2  → Update llm_manager.py (add research_with_web_tools, generate_document_with_skill,
            chat_with_memory, _track_usage_extended)
Phase 3  → Update artifact_manager.py (add download_from_anthropic, upload_to_anthropic)
Phase 4  → Update base_agent.py (add research_web, generate_document, read_document_via_api)
Phase 5  → Update each specialist agent (replace direct tool calls → new base class methods)
Phase 6  → Create memory_manager.py + register in main.py
Phase 7  → Update config.yaml (add anthropic_native section, update model string)
Phase 8  → Alembic migration (new columns on artifacts + llm_usage, new memory_log table)
           → alembic upgrade head
Phase 9  → Add FALLBACK ONLY docstrings to pdf_ops/pptx_ops/docx_ops
Phase 10 → pytest server/tests/test_anthropic_api_upgrade.py -v — fix all failures
Phase 11 → Update LLM.md documentation
```

**Hard rules — never violate:**
- Do NOT restart FastAPI, Celery, or Celery Beat.
- Do NOT delete pdf_ops.py, pptx_ops.py, or docx_ops.py — they are fallbacks.
- Do NOT route CSV through Anthropic Skills — csv_ops.py stays as primary.
- Every document generation call MUST implement fallback to legacy libs on Skills failure.
- Memory tool MUST be scoped per entity — never mix user and agent memory.
- Anthropic file_ids MUST be deleted from Anthropic Files API after download
  (set auto_delete_after_download: true in config).
- All Alembic migrations use ADD COLUMN IF NOT EXISTS and CREATE TABLE IF NOT EXISTS guards.
- Update model string from claude-sonnet-4-5-20250929 → claude-sonnet-4-6 in config.yaml ONLY
  (not hardcoded anywhere in Python files).
