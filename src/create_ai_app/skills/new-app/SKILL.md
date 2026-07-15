# new-app

Scaffold a new Python AI/GenAI project using `new-ai-app`, with optional AI-powered use-case interview.

## Trigger phrases

- "create a new app"
- "scaffold a project"
- "new project"
- "new-ai-app"
- "scaffold a new"
- "start a new"

## What this skill does

Interviews the user about their use case, generates a context file with domain-specific configuration and content, then runs `new-ai-app --context-file` so the scaffolder starts with intelligent defaults. The user still sees and can edit every question before confirming.

---

## Instructions

### Step 1 — Interview

Ask the user these questions (one message, not four separate prompts):

> To generate a project that fits your use case, I have a few quick questions:
>
> 1. **What does this app do?** (2-3 sentences)
> 2. **Who uses it and how?** (e.g. internal employees via Teams, external customers via web UI, other services via API)
> 3. **What data or systems does it need to connect to?** (e.g. SharePoint, SQL database, REST APIs, none)
> 4. **Any constraints?** (e.g. must run on Azure, Teams-only, regulated industry, real-time responses)

Wait for their answers before proceeding.

---

### Step 2 — Generate context

Based on the answers, reason through:

**Technical config** (`recommended_config`):
- `app_types`: `["REST API"]`, `["Agent"]`, `["REST API", "Agent"]`, `["Teams Bot"]`, `["REST API", "Agent", "Teams Bot"]`, etc.
- `agent_framework`: `"Microsoft AF"` if multi-agent / Teams / enterprise; `"None — raw SDK"` otherwise
- `llm_backend`: `"Azure OpenAI"` always (Accenture standard)
- `database`: `"CosmosDB"` if session state needed; `"None — stateless"` otherwise
- `infra`: `"Azure Container Apps — Bicep"` always
- `environments`: `"dev,qa,prd"` for enterprise; `"dev,prd"` for smaller

**Domain content** (`ai_content`):
- `system_prompt`: 3-5 sentences, captures persona + domain + constraints
- `triage_prompt` / `specialist_prompt`: only if multi-agent (MAF)
- `agent_names`: domain-specific (e.g. `["HRTriage", "PolicySpecialist"]` not `["Triage", "Specialist"]`)
- `tools`: 2-4 tools that match the data sources mentioned. Each with `name` (snake_case), `description` (one sentence), `parameters` (list of `{name, type, description}`)
- `request_fields`: 2-4 Pydantic fields matching the request shape
- `response_fields`: 2-3 Pydantic fields matching the response shape

Produce the context as a JSON object. Then write it to the scratchpad:

```python
import json, pathlib
ctx = { ... }  # the full context object
path = pathlib.Path("/tmp/new-ai-app-context.json")
path.write_text(json.dumps(ctx, indent=2))
```

Show the user a brief summary of what was generated:
- App type and framework choices with one-line rationale
- Agent names (if applicable)
- Tools list
- Schema fields

---

### Step 3 — Run the CLI

Tell the user to run (use `!` prefix so it executes in the session):

```
! new-ai-app --context-file /tmp/new-ai-app-context.json
```

Or with a name pre-filled:

```
! new-ai-app my-project-name --context-file /tmp/new-ai-app-context.json
```

The CLI will show all sections with the recommended choices pre-selected. The user can edit any section via the re-entry loop before confirming.

---

### Step 4 — After scaffold

Once they confirm the scaffold completed:

- If infra is **Azure Container Apps — Bicep**: offer to run `/az-setup` to configure the Azure context.
- Remind them:
  ```
  cd <project-name>
  cp .env.example .env   # fill in credentials
  uv run pytest
  uv run uvicorn main:app --reload --port 3100   # REST API
  ```

---

## Context file schema

```json
{
  "suggested_name": "kebab-case-name",
  "recommended_config": {
    "app_types": ["REST API", "Agent"],
    "llm_backend": "Azure OpenAI",
    "agent_framework": "Microsoft AF",
    "database": "CosmosDB",
    "infra": "Azure Container Apps — Bicep",
    "environments": "dev,qa,prd"
  },
  "ai_content": {
    "system_prompt": "You are an HR policy assistant...",
    "triage_prompt": "You are the entry point for HR queries...",
    "specialist_prompt": "You are a policy specialist...",
    "agent_names": ["HRTriage", "PolicySpecialist"],
    "tools": [
      {
        "name": "search_policies",
        "description": "Search company policy documents in SharePoint",
        "parameters": [
          {"name": "query", "type": "str", "description": "Search query"}
        ]
      }
    ],
    "request_fields": [
      {"name": "question", "type": "str", "required": true, "description": "Employee question"},
      {"name": "employee_id", "type": "str | None", "required": false, "description": "Employee ID for context"}
    ],
    "response_fields": [
      {"name": "answer", "type": "str", "description": "Answer to the question"},
      {"name": "policy_references", "type": "list[str]", "description": "Referenced policy documents"}
    ]
  }
}
```

---

## Key decisions the tool enforces

| Without scaffold | With scaffold |
|---|---|
| `requirements.txt` + pip | `uv` + `pyproject.toml` |
| Root-level spaghetti | `src/<pkg>/` layout |
| Hardcoded API key | `.env.example` + APP_API_KEY pattern |
| No auth on API | APP_API_KEY header check |
| Multi-stage Dockerfile missing | Multi-stage slim + non-root + HEALTHCHECK |
| `print()` for logging | `configure_logging()` + LOG_LEVEL env var |
| No tests | `tests/` + conftest + stubs |
| Generic "example_tool" stubs | Domain-specific tools from the interview |
| "You are a helpful assistant" | Proper system prompt capturing domain + persona |

## Tool location

The tool lives at `~/create-ai-app/` and is globally installed as `new-ai-app`.

To reinstall after changes:
```sh
uv tool install --reinstall ~/create-ai-app
```
