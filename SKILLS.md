---
name: oyd-to-foundry-migration
description: "**WORKFLOW SKILL** — Migrate Azure OpenAI On Your Data (OYD) configurations to Azure AI Foundry Agent Service. WHEN: \"migrate OYD to Foundry\", \"create Foundry agent from OYD\", \"OYD migration\", \"convert OYD to agent\", \"search tool agent\", \"knowledge base migration\". INVOKES: Azure CLI, REST APIs (Foundry Agent Service, Azure AI Search), run_migration.py script. FOR SINGLE OPERATIONS: use Azure AI Foundry portal directly for manual agent creation."
---

# Skills Reference

This document provides guidance for both **coding agents** (GitHub Copilot, Claude Code, etc.)
and **human operators** performing OYD-to-Foundry migrations. It covers when to use each
migration path, how to execute each one, and SDK references for integration work.

> **Coding agents:** Start at [Path 1 — Coding Agent](#path-1--coding-agent-programmatic-rest-api).
> Do **not** attempt to drive the interactive wizard — it requires a real TTY.

---

## Migration Path Decision Matrix

| Scenario | Use This Path |
|----------|--------------|
| Running from a coding agent / CI/CD pipeline | **Coding Agent Path** (REST API script) |
| Fully automated batch migration | **Coding Agent Path** (REST API script) |
| Interactive human-guided migration | **Human Wizard Path** (`oyd-migrator wizard`) |
| First-time migration with unknown config | **Human Wizard Path** — wizard prompts for details |
| Known OYD config, scripted repeat migration | **Coding Agent Path** |

> **Why two paths?** The CLI wizard uses `questionary` for interactive prompts (arrow-key
> selection, spinners) which requires a real TTY. Coding agents and CI/CD pipelines do not
> have a TTY, so they must use the direct REST API script instead.

---

## Path 1 — Coding Agent (Programmatic REST API)

Use this path when running from a coding agent, CI/CD, or any non-interactive environment.

### Prerequisites

Before running, confirm these Azure resources exist:

```bash
# 1. Verify Azure CLI is authenticated
az account show

# 2. Confirm OYD source works (replace with your values)
az cognitiveservices account show --name <your-aoai-resource> --resource-group <rg> --query "properties.endpoint"

# 3. Confirm search index exists (az search index show does NOT exist in current CLI)
#    Use the REST API with an admin key instead:
ADMIN_KEY=$(az search admin-key show --service-name <your-search-service> --resource-group <rg> --query primaryKey -o tsv)
curl -s -H "api-key: $ADMIN_KEY" "https://<your-search-service>.search.windows.net/indexes/<index-name>?api-version=2024-07-01" | python -c "import sys,json; d=json.load(sys.stdin); print(d['name'], '-', len(d.get('fields',[])), 'fields')"
#    PowerShell: $adminKey = az search admin-key show --service-name <svc> --resource-group <rg> --query primaryKey -o tsv
#    curl -H "api-key: $adminKey" "https://<svc>.search.windows.net/indexes/<index>?api-version=2024-07-01"

# 4. Confirm Foundry project endpoint resolves
# Must be a CognitiveServices/AIServices account, NOT an ML Workspace Hub
az cognitiveservices account show --name <your-foundry-resource> --resource-group <rg> --query "kind"
# Expected output: "AIServices"

# 5. Confirm model is deployed in the Foundry project
az cognitiveservices account deployment show --name <your-foundry-resource> --resource-group <rg> --deployment-name gpt-4.1-mini
```

**Required Azure resources (must be pre-provisioned):**

| Resource | Type | Notes |
|----------|------|-------|
| Azure AI Search service | `Microsoft.Search/searchServices` | With indexed data |
| Foundry account | `Microsoft.CognitiveServices/accounts` (kind: `AIServices`) | NOT an ML Workspace Hub |
| Foundry project | Project under the Foundry account | |
| Model deployment | `gpt-4.1-mini` (recommended), `gpt-4.1`, `gpt-4.1-nano`, `gpt-4o-mini`, or `gpt-4o` in the project | |
| Search connection | Connected resource in the Foundry project | Create via portal before running script |

**RBAC roles required:**

| Role | Scope |
|------|-------|
| `Cognitive Services OpenAI User` | AOAI resource (for OYD validation queries) |
| `Azure AI User` | Foundry project (for agent CRUD) |
| `Search Index Data Reader` | Search service (for agent to query index) |
| `Search Service Contributor` | Search service (for index metadata) |

> **Note:** The AI Services managed identity (not your user identity) needs
> `Search Index Data Reader` and `Search Service Contributor` on the search resource.
> RBAC propagation can take 5–10 minutes after assignment.

### How to Create the Search Connection

The project **data-plane** API does not support connection creation (returns 405).
You have two options:

**Option A — Portal (simplest):**
1. Go to https://ai.azure.com → select your project
2. **Management** → **Connected resources** → **+ New connection**
3. Select **Azure AI Search** → choose your search service
4. Set auth to **API Key** or **Microsoft Entra ID**
5. Note the connection name (use this as `SEARCH_CONNECTION_NAME`)

**Option B — ARM Management API (automatable):**
The `ConnectionManagerService` in `oyd_migrator/services/connection_manager.py` creates
connections via the ARM management API (`api-version=2024-07-01-preview`) using
`https://management.azure.com/.default` scope. This is suitable for CI/CD pipelines.

### Execute the Migration

```bash
# Clone and install
git clone https://github.com/farzad528/azure-openai-on-your-data-migrator.git
cd azure-openai-on-your-data-migrator
pip install -e .

# Set environment variables (do NOT edit the script directly)
export FOUNDRY_PROJECT_ENDPOINT="https://<foundry-resource>.services.ai.azure.com/api/projects/<project-name>"
export FOUNDRY_MODEL="gpt-4.1-mini"               # Must match a deployed model in the project
export SEARCH_CONNECTION_NAME="my-search"           # Connection name created in portal/ARM
export SEARCH_INDEX_NAME="my-index"                 # Azure AI Search index name
export SEARCH_QUERY_TYPE="semantic"                 # simple | semantic | vector | vector_simple_hybrid | vector_semantic_hybrid
export AGENT_NAME="my-migrated-agent"
export AGENT_INSTRUCTIONS="You are a helpful assistant. Use the search tool to find information before answering."

# Optional: OYD source for side-by-side comparison
export OYD_ENDPOINT="https://<aoai-resource>.openai.azure.com"
export OYD_DEPLOYMENT="gpt-4o-mini"
export AZURE_SEARCH_KEY="<search-api-key>"          # Never hardcode; use env var

# Run
python scripts/run_migration.py
```

### Configuration Reference

| Environment Variable | Example | Notes |
|---------------------|---------|-------|
| `FOUNDRY_PROJECT_ENDPOINT` | `https://myresource.services.ai.azure.com/api/projects/myproject` | Required |
| `FOUNDRY_MODEL` | `gpt-4.1-mini` | Must be deployed in project |
| `SEARCH_CONNECTION_NAME` | `my-search` | From portal or ARM |
| `SEARCH_INDEX_NAME` | `my-index` | Azure AI Search index |
| `SEARCH_QUERY_TYPE` | `semantic` | `simple \| semantic \| vector \| vector_simple_hybrid \| vector_semantic_hybrid` |
| `AGENT_NAME` | `oyd-migrated-agent` | Optional, has default |
| `AGENT_INSTRUCTIONS` | `"You are a helpful assistant..."` | Maps from OYD `role_information` |

### Key API Facts for Coding Agents

```python
# ✅ Correct token scope for Foundry Agent Service
token = credential.get_token("https://ai.azure.com/.default")

# ✅ Correct API versions:
#   - run_migration.py (standalone script): API_VERSION = "2025-05-01"
#   - agent_builder.py (library):           API_VERSION = "v1"
#   - connection_manager.py (connections):  API_VERSION = "2024-07-01-preview"

# ✅ Correct endpoint format
# https://{resource-name}.services.ai.azure.com/api/projects/{project-name}

# ✅ Recommended models (in order): gpt-4.1-mini, gpt-4.1, gpt-4.1-nano, gpt-4o-mini, gpt-4o

# ❌ Wrong — old API version (returns 400 on newer accounts)
# API_VERSION = "2024-07-01-preview"

# ❌ Wrong — ML scope (returns 401 with "audience is incorrect")
# token = credential.get_token("https://management.azure.com/.default")
# (Exception: connection_manager.py correctly uses management scope for ARM calls)
```

### Verify Success

After the script completes, verify the migrated agent:

```bash
# Get token
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

# List agents in the project
curl "https://<foundry-resource>.services.ai.azure.com/api/projects/<project>/assistants?api-version=2025-05-01" \
  -H "Authorization: Bearer $TOKEN"

# Or open the portal playground:
# https://ai.azure.com → your project → Agents → your agent → Playground
```

**PowerShell equivalent:**
```powershell
$TOKEN = az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv
curl "https://<foundry-resource>.services.ai.azure.com/api/projects/<project>/assistants?api-version=2025-05-01" `
  -H "Authorization: Bearer $TOKEN"
```

### Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `404` on agent creation | ARM-to-data-plane propagation delay | Script retries 3x (10s, 20s, 30s). Wait and re-run if needed. |
| `401 audience is incorrect` | Wrong token scope | Use `https://ai.azure.com/.default`, not management scope |
| `400` on API call | Wrong API version | Use `2025-05-01` for standalone script, `v1` for SDK library |
| Agent returns empty results | Missing RBAC on search | Assign `Search Index Data Reader` + `Search Service Contributor` to AI Services MI |
| `405` on connection creation | Using data-plane for connections | Use portal or ARM management API (see connection section above) |
| `ImportError` azure-mgmt-resource | Version 25.x breaking change | Pinned to `>=23.0.0,<25.0.0` in pyproject.toml |

### Model Selection Guide

Tested live with identical queries against the `hrdocs` index (semantic search, 3 queries each):

| Model | Avg Latency | Avg Response Length | Citations | Success Rate | Recommendation |
|-------|-------------|--------------------:|----------:|-------------:|----------------|
| **`gpt-4.1-mini`** | **4.4s** | **1068 chars** | **6** | 100% | **Best overall — fastest, most detailed, most grounded** |
| `gpt-4.1` | 6.9s | 863 chars | 0 | 100% | Thorough but slower; fewer inline citations |
| `gpt-4o-mini` | 7.1s | 987 chars | 4 | 100% | Good fallback; ~60% slower than gpt-4.1-mini |

**Key observations:**
- **`gpt-4.1-mini` is the recommended model** — it was fastest (4.4s avg), produced the longest responses (1068 chars avg), and returned the most search citations (6 total). It consistently grounded answers in the indexed documents.
- **`gpt-4.1`** produced well-structured responses but was 57% slower and returned zero inline citations, indicating it synthesized answers from search context without referencing specific documents.
- **`gpt-4o-mini`** was the slowest (7.1s avg) and returned mid-range citation counts. Viable as a fallback if gpt-4.1-mini is unavailable.
- All three models achieved 100% success rate — agent creation, thread/run execution, and search tool invocation all worked reliably.
- Agent creation time was consistently ~1s across all models (not model-dependent).

> **For coding agents:** Default to `gpt-4.1-mini`. Only switch to `gpt-4.1` if you need higher reasoning quality and can tolerate higher latency. Use `gpt-4o-mini` as a last resort.

---

## Path 1b — Knowledge Base Migration (Coding Agent)

For complex queries or multi-source scenarios, use the Foundry IQ Knowledge Base path
instead of the Search Tool path. This uses MCP (Model Context Protocol) under the hood.

### When to Use Knowledge Base vs Search Tool

| Criteria | Search Tool | Knowledge Base |
|----------|-------------|----------------|
| Simple RAG, single index | ✅ Recommended | Works |
| GA stability required | ✅ Recommended | Preview |
| Complex queries, multi-source | Works | ✅ Recommended |
| SharePoint/OneLake sources | Not supported | ✅ Recommended |
| Semantic reranking built-in | Manual config | ✅ Automatic |

### Key Differences in Agent Creation

```python
# Search Tool agent — uses azure_ai_search tool type
tools = [{"type": "azure_ai_search"}]
tool_resources = {
    "azure_ai_search": {
        "indexes": [{"index_connection_id": conn_id, "index_name": "my-index", ...}]
    }
}

# Knowledge Base agent — uses MCP tool type
# MCP endpoint: {search_endpoint}/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview
tools = [{
    "type": "mcp",
    "server_label": "my_kb",
    "server_url": "https://my-search.search.windows.net/knowledgebases/my-kb/mcp?api-version=2025-11-01-preview",
    "require_approval": "never",
    "allowed_tools": ["knowledge_base_retrieve"],
    "project_connection_id": conn_id,
}]
```

### OYD Parameter Mapping for Knowledge Base

| OYD Parameter | KB Equivalent | Notes |
|--------------|---------------|-------|
| `strictness` (1-5) | `reranker_score_threshold` (0.0-4.0) | Formula: `(strictness - 1) * 1.0` |
| `semantic_configuration` | Built-in semantic reranking | Inherited automatically |
| `top_n_documents` | `top_k` on retrieve call | Same concept |
| `role_information` | Agent `instructions` | Direct mapping |
| `in_scope: true` | Append grounding constraint to instructions | Manual enforcement |

---

---

## Coding Agent Guidelines

When a coding agent (GitHub Copilot, Claude Code, etc.) assists with migration:

1. **Do not attempt to drive the interactive wizard** — `questionary` requires a real TTY.
   Use `scripts/run_migration.py` or direct REST API calls instead.

2. **Always check the Foundry resource type first:**
   ```bash
   az cognitiveservices account show --name <name> --resource-group <rg> --query "kind"
   # Must return "AIServices", not an ML Workspace Hub
   ```

3. **Create the search connection before running the script:**
   - **Portal:** Management → Connected resources → + New connection (simplest)
   - **ARM API:** Use `ConnectionManagerService.create_search_connection()` via management
     scope (`api-version=2024-07-01-preview`). Do NOT use the project data-plane (returns 405).

4. **Use the correct token scopes:**
   - Agent CRUD: `https://ai.azure.com/.default`
   - Connection management: `https://management.azure.com/.default`
   - OYD comparison queries: `https://cognitiveservices.azure.com/.default`

5. **Use environment variables** — Do not edit `scripts/run_migration.py` directly.
   Set `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `SEARCH_CONNECTION_NAME`, etc.

6. **Validate side-by-side** — The script automatically queries both the original OYD source
   and the new Foundry agent with the same queries and compares results. Set `OYD_ENDPOINT`
   and `AZURE_SEARCH_KEY` environment variables to enable comparison.

7. **Handle ARM propagation delays** — After connection creation, the data-plane may take
   15+ seconds to see the connection. The agent builder retries 3x with 10s/20s/30s delays.
   If creation still fails, wait and re-run.

8. **Run tests** to validate the codebase after changes:
   ```bash
   pytest tests/                          # All tests
   pytest tests/functional/               # Functional tests only
   pytest tests/integration/              # Integration tests (needs Azure creds)
   ```

9. **Check `docs/KNOWN_LIMITATIONS.md`** for full details on edge cases and workarounds.

---

## Azure SDK Skills

For SDK-specific guidance, patterns, and best practices, refer to the Microsoft-maintained
Copilot Skills:

### Azure AI Search

| Language | Skill |
|----------|-------|
| Python | [azure-search-documents-py](https://github.com/microsoft/skills/tree/main/.github/skills/azure-search-documents-py) |
| TypeScript | [azure-search-documents-ts](https://github.com/microsoft/skills/tree/main/.github/skills/azure-search-documents-ts) |
| .NET | [azure-search-documents-dotnet](https://github.com/microsoft/skills/tree/main/.github/skills/azure-search-documents-dotnet) |

### Azure OpenAI

| Language | Skill |
|----------|-------|
| .NET | [azure-ai-openai-dotnet](https://github.com/microsoft/skills/tree/main/.github/skills/azure-ai-openai-dotnet) |

### Azure AI Foundry Projects

| Language | Skill |
|----------|-------|
| Python | [azure-ai-projects-py](https://github.com/microsoft/skills/tree/main/.github/skills/azure-ai-projects-py) |

These skills are managed by Microsoft at [github.com/microsoft/skills](https://github.com/microsoft/skills).
Attach the relevant skill when working on service integration code.

