# LLM.md — Claude + Kimi LLM Layer

**Dual-LLM system using Claude (Anthropic) for primary reasoning and Kimi (Moonshot) for Chinese/Asia-Pacific content.**

---

## Overview

```
/server/app/llm
├── llm_manager.py           # Orchestrator — routes between Claude and Kimi
├── anthropic_client.py      # Claude API client
└── kimi_client.py           # Kimi / Moonshot API client
```

---

## Architecture

```
Request + Department Context
    │
    ▼
┌────────────────────────────────────┐
│          LLM MANAGER               │
│  • Selects model based on task     │
│  • Manages tool calling loop       │
│  • Handles failover                │
│  • Tracks token usage              │
└────────┬───────────┬───────────────┘
         │           │
         ▼           ▼
┌────────────┐ ┌─────────────┐
│   Claude   │ │    Kimi     │
│ (Anthropic)│ │ (Moonshot)  │
│            │ │             │
│ Primary:   │ │ Primary:    │
│ • English  │ │ • Chinese   │
│ • Complex  │ │ • Mandarin  │
│   reasoning│ │   content   │
│ • Document │ │ • APAC      │
│   generation│ │   market    │
│ • Tool     │ │   research  │
│   calling  │ │ • Long      │
│ • Analysis │ │   context   │
└────────────┘ └─────────────┘
```

---

## Model Selection Logic

The LLM Manager selects the model based on task characteristics:

| Signal | Route to | Reason |
|--------|----------|--------|
| Default (all tasks) | **Claude** | Primary model — best reasoning and tool use |
| Chinese language content | **Kimi** | Native Chinese understanding and generation |
| Chinese market research | **Kimi** | Better access to Chinese business context |
| Mandarin email/content drafting | **Kimi** | Natural Chinese writing |
| Claude rate limited / unavailable | **Kimi** | Failover |
| Kimi rate limited / unavailable | **Claude** | Failover |

### Decision Flow

```python
def select_model(self, task):
    # Detect language
    if self._contains_chinese(task["message"]):
        return self.kimi

    # Check for APAC / Chinese market context
    if self._is_chinese_market_task(task):
        return self.kimi

    # Default to Claude for everything else
    return self.claude
```

---

## LLM Manager (`llm_manager.py`)

Central orchestrator for both LLM backends.

### Initialization

```python
class LLMManager:
    def __init__(self, config):
        self.claude = AnthropicClient(
            api_key=config["llm"]["claude"]["api_key"],
            model=config["llm"]["claude"]["model"],  # claude-sonnet-4-5-20250929
            max_tokens=config["llm"]["claude"]["max_tokens"],
        )
        self.kimi = KimiClient(
            api_key=config["llm"]["kimi"]["api_key"],
            model=config["llm"]["kimi"]["model"],  # moonshot-v1-128k
            max_tokens=config["llm"]["kimi"]["max_tokens"],
        )
        self.tool_executor = ToolExecutor(config)
```

### Tool Calling Loop

Both Claude and Kimi support tool/function calling. The manager runs an agentic loop:

```python
async def execute_with_tools(self, task, tools, max_iterations=5):
    model = self.select_model(task)
    tool_defs = self.tool_executor.get_definitions(tools)
    messages = self._build_messages(task)

    for i in range(max_iterations):
        response = await model.chat(messages, tool_defs)

        if response.get("tool_calls"):
            # Execute tools
            results = await self.tool_executor.execute_many(response["tool_calls"])

            # Append to conversation for next iteration
            messages.append({"role": "assistant", "tool_calls": response["tool_calls"]})
            for result in results:
                messages.append({"role": "tool", "content": result["output"], ...})
        else:
            return response["content"]  # Final answer

    return "Task exceeded maximum steps"
```

### System Prompt

The system prompt is department-aware and adapts to the task source:

```
You are the Mezzofy AI Assistant helping the {department} team.

You have access to tools for:
- Sending emails via Outlook (Microsoft Graph API)
- Creating/reading calendar events in Outlook
- Posting messages to MS Teams channels
- Generating PDFs, slide decks, and documents
- Searching the web and LinkedIn
- Querying Mezzofy's internal data (products, pricing, features)
- Managing the CRM / sales lead database
- Querying financial and operational databases

Department context: {department}
User role: {role}
Task source: {source}  # mobile | scheduler | webhook

Be professional, concise, and action-oriented. When generating customer-facing
content, use Mezzofy brand voice. When sending emails via Outlook, always confirm
with the user before sending unless they explicitly said "auto send" or this is
a scheduled/webhook task (auto-send is allowed for automated workflows).

When delivering scheduled report results, format them for MS Teams with clear
headings and attach generated files.
```

---

## Claude Client (`anthropic_client.py`)

### Configuration

```yaml
llm:
  claude:
    provider: "anthropic"
    model: "claude-sonnet-4-5-20250929"
    api_key: "${ANTHROPIC_API_KEY}"
    max_tokens: 4096
    temperature: 0.7
```

### Capabilities

- Native tool/function calling with structured definitions
- Multi-turn conversation with full history
- Streaming support for real-time WebSocket updates
- Strong at complex reasoning, document generation, data analysis

---

## Kimi Client (`kimi_client.py`)

### Configuration

```yaml
llm:
  kimi:
    provider: "moonshot"
    model: "moonshot-v1-128k"
    api_key: "${KIMI_API_KEY}"
    base_url: "https://api.moonshot.cn/v1"
    max_tokens: 4096
    temperature: 0.7
```

### Capabilities

- OpenAI-compatible API format (simplifies integration)
- 128K context window — excellent for long documents
- Native Chinese language understanding and generation
- Tool/function calling support
- Strong at Chinese business content and APAC market research

### Client Pattern

Since Kimi uses an OpenAI-compatible API:

```python
from openai import AsyncOpenAI

class KimiClient:
    def __init__(self, config):
        self.client = AsyncOpenAI(
            api_key=config["api_key"],
            base_url="https://api.moonshot.cn/v1",
        )
        self.model = config["model"]

    async def chat(self, messages, tools=None):
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            temperature=0.7,
        )
        return self._parse_response(response)
```

---

## Failover & Error Handling

```
Primary model fails (rate limit, timeout, API error)
    │
    ├── Retry once with backoff
    ├── If still fails → failover to other model
    ├── If both fail → return error to user with retry suggestion
    └── Log all failures for monitoring
```

### Token Usage Tracking

The LLM Manager tracks token usage per model, per department, per user for cost monitoring:

```python
async def _track_usage(self, model_name, department, user_id, input_tokens, output_tokens):
    await self.db.execute("""
        INSERT INTO llm_usage (model, department, user_id, input_tokens, output_tokens, timestamp)
        VALUES ($1, $2, $3, $4, $5, NOW())
    """, model_name, department, user_id, input_tokens, output_tokens)
```

This data feeds into the Management Agent's cost dashboards.

---

## Configuration Summary

```yaml
# config/config.yaml → llm section
llm:
  default_model: "claude"       # Primary model for all tasks
  fallback_model: "kimi"        # Failover model

  claude:
    provider: "anthropic"
    model: "claude-sonnet-4-5-20250929"
    api_key: "${ANTHROPIC_API_KEY}"
    max_tokens: 4096
    temperature: 0.7

  kimi:
    provider: "moonshot"
    model: "moonshot-v1-128k"
    api_key: "${KIMI_API_KEY}"
    base_url: "https://api.moonshot.cn/v1"
    max_tokens: 4096
    temperature: 0.7

  routing:
    chinese_content: "kimi"
    apac_research: "kimi"
    default: "claude"
```
