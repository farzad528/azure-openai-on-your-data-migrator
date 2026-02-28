---
name: oyd-to-foundry-migration
description: "**WORKFLOW SKILL** — Migrate Azure OpenAI On Your Data (OYD) to AI Foundry Agent Service. WHEN: \"migrate OYD to Foundry\", \"create Foundry agent from OYD\", \"OYD migration\", \"convert OYD to agent\", \"search tool agent\", \"knowledge base migration\". INVOKES: Azure CLI, REST APIs, run_migration.py. FOR SINGLE OPERATIONS: use AI Foundry portal directly."
---

# Skills Reference

This document provides guidance for both **coding agents** (GitHub Copilot, Claude Code, etc.)
and **human operators** performing OYD-to-Foundry migrations. It covers when to use each
migration path, how to execute each one, and SDK references for integration work.

> **Coding agents:** Start at [Coding Agent Path](#coding-agent-path-programmatic-rest-api).
> Do **not** attempt to drive the interactive wizard — it requires a real TTY.

---

## Migration Path Decision Matrix

| Scenario | Use This Path |
|----------|--------------|
| Running from a coding agent / CI/CD pipeline | **Coding Agent Path** (REST API script) — see [below](#coding-agent-path-programmatic-rest-api) |
| Fully automated batch migration | **Coding Agent Path** (REST API script) |
| Interactive human-guided migration | **Human Wizard Path** (`oyd-migrator wizard`) — see [README.md](../../../README.md) and [AGENTS.md](../../../AGENTS.md) for wizard instructions |
| First-time migration with unknown config | **Human Wizard Path** — see [docs/MIGRATION_GUIDE.md](../../../docs/MIGRATION_GUIDE.md) |
| Known OYD config, scripted repeat migration | **Coding Agent Path** |

> **Note:** The CLI wizard (`oyd-migrator wizard`) uses `questionary` for interactive prompts
> which requires a real TTY — coding agents and CI/CD pipelines cannot use it.
> For wizard instructions see [README.md](../../../README.md) and [AGENTS.md](../../../AGENTS.md).
> This file covers the programmatic (REST API) approach only.

---

## Coding Agent Path (Programmatic REST API)

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
#    curl.exe -H "api-key: $adminKey" "https://<svc>.search.windows.net/indexes/<index>?api-version=2024-07-01"

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
| `Contributor` | Foundry project (only if creating connections or projects via ARM) |

> **Note:** The AI Services managed identity (not your user identity) needs
> `Search Index Data Reader` and `Search Service Contributor` on the search resource.
> RBAC propagation can take 5–10 minutes after assignment.

### Step 0: Discover Existing OYD Configuration

Before migrating, extract the OYD configuration from the source deployment.
OYD is configured **inline at the API call level** (not as a persistent deployment property),
so it cannot be auto-detected from the Azure management API alone.

**Strategy 1 — Extract from application code (recommended):**
Search the user's codebase for the `data_sources` payload sent to the AOAI chat completions API:

```bash
# Look for OYD configuration in the codebase
grep -r "data_sources" --include="*.py" --include="*.js" --include="*.ts" --include="*.json" --include="*.yaml" .
grep -r "azure_search\|AzureSearchChatExtensionConfiguration" --include="*.py" --include="*.cs" .
```

The configuration typically looks like:
```json
{
  "data_sources": [{
    "type": "azure_search",
    "parameters": {
      "endpoint": "https://my-search.search.windows.net",
      "index_name": "my-index",
      "query_type": "semantic",
      "semantic_configuration": "default",
      "fields_mapping": {
        "content_fields": ["content"],
        "title_field": "title",
        "url_field": "url"
      },
      "role_information": "You are an HR assistant...",
      "strictness": 3,
      "top_n_documents": 5,
      "in_scope": true
    }
  }]
}
```

Extract these values and map them to environment variables:

| OYD `parameters` Field | Maps To | Notes |
|------------------------|---------|-------|
| `endpoint` | `SEARCH_CONNECTION_NAME` | DNS prefix (e.g., `my-search` from `https://my-search.search.windows.net`) |
| `index_name` | `SEARCH_INDEX_NAME` | Direct mapping |
| `query_type` | `SEARCH_QUERY_TYPE` | `simple` \| `semantic` \| `vector` \| `vector_simple_hybrid` \| `vector_semantic_hybrid` |
| `role_information` | `AGENT_INSTRUCTIONS` | Direct mapping — use the exact text |
| `strictness` | N/A (Search Tool) | Not configurable in agent API; KB path: `(strictness - 1) * 1.0` |
| `top_n_documents` | Hardcoded `top_k: 5` in script | Editable in `run_migration.py` |
| `fields_mapping` | N/A | Agent API does not accept field mappings — search index schema determines field behavior |
| `in_scope` | Append to `AGENT_INSTRUCTIONS` | Add: "Only answer from the search results. If the information is not found, say so." |
| `semantic_configuration` | N/A (Search Tool) | Inherited from search index; KB path: automatic |

**Strategy 2 — Probe via Azure CLI (best-effort):**

```bash
# List all OpenAI resources in a resource group
az cognitiveservices account list -g <rg> --query "[?kind=='OpenAI'].{name:name, endpoint:properties.endpoint}" -o table

# List deployments on an AOAI resource
az cognitiveservices account deployment list --name <aoai-resource> -g <rg> --query "[].{name:name, model:properties.model.name, version:properties.model.version}" -o table

# Test an OYD query to verify configuration (requires the data_sources payload)
TOKEN=$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)
curl -X POST "https://<aoai-resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=2024-10-21" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}],"data_sources":[{"type":"azure_search","parameters":{"endpoint":"https://<search>.search.windows.net","index_name":"<index>","authentication":{"type":"system_assigned_managed_identity"},"query_type":"semantic"}}]}'
```

> **Key insight:** The interactive wizard's `AOAIDiscoveryService` uses the same best-effort
> approach and frequently falls back to asking the user for manual input. A coding agent
> should prioritize Strategy 1 (searching the codebase) for reliable config extraction.

### How to Create the Search Connection

The project **data-plane** API does not support connection creation (returns 405).
You have two options:

**Option A — Portal (simplest):**
1. Go to https://ai.azure.com → select your project
2. **Management** → **Connected resources** → **+ New connection**
3. Select **Azure AI Search** → choose your search service
4. Set auth to **API Key** or **Microsoft Entra ID**
5. Note the connection name (use this as `SEARCH_CONNECTION_NAME`)

**Option B — ARM REST API (fully automated):**

Create a connection via the ARM management API. This requires `Contributor` role on the Foundry project.

**Choose an auth type:**
- **`ApiKey`** — Simpler setup; search service API key is stored in the connection. Works with any search service auth mode.
- **`AAD`** — Uses Foundry managed identity; requires the search service to allow RBAC access (`aadOrApiKey` or `rbac`) and the managed identity to have `Search Index Data Reader` + `Search Service Contributor` roles on the search resource.

```bash
# Set variables
SUBSCRIPTION_ID="<subscription-id>"
RESOURCE_GROUP="<resource-group>"
FOUNDRY_RESOURCE="<foundry-resource-name>"
PROJECT_NAME="<project-name>"
CONNECTION_NAME="<search-service-name>"  # Must match search DNS prefix
SEARCH_ENDPOINT="https://${CONNECTION_NAME}.search.windows.net"
AUTH_TYPE="ApiKey"  # or "AAD"

# Get ARM token
ARM_TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

# For ApiKey auth, get the search admin key:
SEARCH_KEY=$(az search admin-key show --service-name ${CONNECTION_NAME} \
  --resource-group ${RESOURCE_GROUP} --query primaryKey -o tsv)

# Create search connection via ARM PUT
# ApiKey variant (includes credentials block):
curl -X PUT \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${FOUNDRY_RESOURCE}/projects/${PROJECT_NAME}/connections/${CONNECTION_NAME}?api-version=2025-04-01-preview" \
  -H "Authorization: Bearer ${ARM_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"properties\": {
      \"category\": \"CognitiveSearch\",
      \"target\": \"${SEARCH_ENDPOINT}\",
      \"authType\": \"${AUTH_TYPE}\",
      \"isSharedToAll\": true,
      \"credentials\": { \"key\": \"${SEARCH_KEY}\" }
    }
  }"
# For AAD auth, omit the "credentials" block entirely.
```

**PowerShell equivalent (ApiKey):**
```powershell
$armToken = az account get-access-token --resource https://management.azure.com --query accessToken -o tsv
$searchKey = az search admin-key show --service-name $connectionName --resource-group $rg --query primaryKey -o tsv
$uri = "https://management.azure.com/subscriptions/$subscriptionId/resourceGroups/$rg/providers/Microsoft.CognitiveServices/accounts/$foundryResource/projects/$projectName/connections/$connectionName`?api-version=2025-04-01-preview"
$body = @{ properties = @{ category = "CognitiveSearch"; target = $searchEndpoint; authType = "ApiKey"; isSharedToAll = $true; credentials = @{ key = $searchKey } } } | ConvertTo-Json -Depth 3
curl.exe -X PUT $uri -H "Authorization: Bearer $armToken" -H "Content-Type: application/json" -d $body
```

> **Wait 15–30 seconds** after creation for ARM-to-data-plane propagation before running the migration script.

> **Note on `ConnectionManagerService`:** The library's `_build_connection_url()` in
> `oyd_migrator/services/connection_manager.py` currently falls back to the data-plane
> endpoint (returns 405). The ARM curl above is the reliable workaround.

### Execute the Migration

```bash
# Clone and install
git clone https://github.com/farzad528/azure-openai-on-your-data-migrator.git
cd azure-openai-on-your-data-migrator
pip install -e .

# Set environment variables (do NOT edit the script directly)
export FOUNDRY_PROJECT_ENDPOINT="https://<foundry-resource>.services.ai.azure.com/api/projects/<project-name>"
export FOUNDRY_MODEL="gpt-4.1-mini"               # Must match a deployed model in the project
export SEARCH_CONNECTION_NAME="my-search"           # Must equal the Azure AI Search service name (DNS prefix before .search.windows.net) and the Foundry connection name
export SEARCH_INDEX_NAME="my-index"                 # Azure AI Search index name
export SEARCH_QUERY_TYPE="semantic"                 # simple | semantic | vector | vector_simple_hybrid | vector_semantic_hybrid
export AGENT_NAME="my-migrated-agent"

# System message — copy from your OYD role_information (see Step 0: Discovery)
# If OYD used in_scope: true, append grounding constraint to the instructions.
export AGENT_INSTRUCTIONS="You are a helpful assistant. Use the search tool to find information before answering. Only answer from the search results. If the information is not found, say so."

# Optional: OYD source for side-by-side comparison
export OYD_ENDPOINT="https://<aoai-resource>.openai.azure.com"
export OYD_DEPLOYMENT="gpt-4o-mini"
export AZURE_SEARCH_KEY="<search-api-key>"          # Never hardcode; use env var

# Run (idempotent — safe to re-run; creates a new agent each time)
python scripts/run_migration.py

# Batch migration: loop over multiple deployments
# for each OYD deployment, set the env vars and re-run:
#   export AGENT_NAME="agent-deployment-2" SEARCH_INDEX_NAME="index-2" ...
#   python scripts/run_migration.py
```

### Configuration Reference

| Environment Variable | Example | Notes |
|---------------------|---------|-------|
| `FOUNDRY_PROJECT_ENDPOINT` | `https://myresource.services.ai.azure.com/api/projects/myproject` | Required |
| `FOUNDRY_MODEL` | `gpt-4.1-mini` | Must be deployed in project |
| `SEARCH_CONNECTION_NAME` | `my-search` | Must match Azure AI Search service DNS name **and** Foundry connection name |
| `SEARCH_INDEX_NAME` | `my-index` | Azure AI Search index |
| `SEARCH_QUERY_TYPE` | `semantic` | `simple \| semantic \| vector \| vector_simple_hybrid \| vector_semantic_hybrid` |
| `AGENT_NAME` | `oyd-migrated-agent` | Optional, has default |
| `AGENT_INSTRUCTIONS` | `"You are a helpful assistant..."` | Maps from OYD `role_information` — see [Step 0: Discovery](#step-0-discover-existing-oyd-configuration) |

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
curl.exe "https://<foundry-resource>.services.ai.azure.com/api/projects/<project>/assistants?api-version=2025-05-01" `
  -H "Authorization: Bearer $TOKEN"
```

### Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `404` on agent creation | ARM-to-data-plane propagation delay | `agent_builder.py` retries 3x (10s, 20s, 30s). The standalone `run_migration.py` does **not** retry — re-run manually if needed. |
| `401 audience is incorrect` | Wrong token scope | Use `https://ai.azure.com/.default`, not management scope |
| `400` on API call | Wrong API version | Use `2025-05-01` for standalone script, `v1` for SDK library |
| Agent returns empty results | Missing RBAC on search | Assign `Search Index Data Reader` + `Search Service Contributor` to AI Services MI |
| `405` on connection creation | Using data-plane for connections | Use portal or ARM REST API (see [Option B](#how-to-create-the-search-connection)) |
| `ImportError` azure-mgmt-resource | Version 25.x breaking change | Pinned to `>=23.0.0,<25.0.0` in pyproject.toml |
| Duplicate agents after re-run | Script is idempotent but creates new agents | Delete old agents via portal or `DELETE /assistants/{id}` before re-running |

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

## Knowledge Base Migration (Coding Agent)

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

### Generate SDK Samples

After migration, generate client code for integration testing:

```bash
# Generate Python SDK sample for the migrated agent
oyd-migrator generate python <agent-name> --project-endpoint <endpoint>

# Or use the library directly:
python -c "
from oyd_migrator.generators.sdk_samples import generate_python_sample
print(generate_python_sample(
    agent_name='my-migrated-agent',
    project_endpoint='https://myresource.services.ai.azure.com/api/projects/myproject',
    model='gpt-4.1-mini',
))
"
```

### Create Foundry Project (Optional)

If you need to provision a new Foundry project programmatically:

```bash
# Via Azure CLI
az cognitiveservices account create \
  --name <project-name> \
  --resource-group <rg> \
  --kind AIServices \
  --sku S0 \
  --location eastus2
```

> In most cases the project is pre-provisioned. Skip this step if you already have a project endpoint.

---

## Coding Agent Guidelines

When a coding agent (GitHub Copilot, Claude Code, etc.) assists with migration:

1. **Start with discovery** — Run [Step 0](#step-0-discover-existing-oyd-configuration) first.
   Search the user's codebase for `data_sources` payloads to extract OYD configuration.
   Do not ask the user for values that can be found in the code.

2. **Do not attempt to drive the interactive wizard** — `questionary` requires a real TTY.
   Use `scripts/run_migration.py` or direct REST API calls instead.

3. **Always check the Foundry resource type first:**
   ```bash
   az cognitiveservices account show --name <name> --resource-group <rg> --query "kind"
   # Must return "AIServices", not an ML Workspace Hub
   ```

4. **Create the search connection before running the script:**
   - **ARM REST API:** Use the `curl` PUT command in [Option B](#how-to-create-the-search-connection) — fully automated.
   - **Portal fallback:** Management → Connected resources → + New connection.
   - Do NOT use the project data-plane for connection creation (returns 405).

5. **Use the correct token scopes:**
   - Agent CRUD: `https://ai.azure.com/.default`
   - Connection management (ARM): `https://management.azure.com/.default`
   - OYD comparison queries: `https://cognitiveservices.azure.com/.default`

6. **Map OYD config to env vars** — Use the mapping table in Step 0. Copy `role_information`
   to `AGENT_INSTRUCTIONS`. If `in_scope: true`, append a grounding constraint. Field mappings
   are not configurable in the agent API — the search index schema handles them automatically.

7. **Use environment variables** — Do not edit `scripts/run_migration.py` directly.
   Set `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `SEARCH_CONNECTION_NAME`, etc.

8. **Validate side-by-side** — The script queries both the OYD source and the new Foundry
   agent with the same queries and compares results. Set `OYD_ENDPOINT` and `AZURE_SEARCH_KEY`.

9. **Handle ARM propagation delays** — After connection creation, wait 15–30 seconds.
   The agent builder retries 3x (10s/20s/30s). The standalone script does not retry — re-run if needed.

10. **Batch migration** — For multiple OYD deployments, loop: set different env vars per
    deployment and run `python scripts/run_migration.py` for each. The script is idempotent.

11. **Generate SDK samples** after migration for integration testing:
    `oyd-migrator generate python <agent-name> --project-endpoint <endpoint>`

12. **Run tests** to validate the codebase after changes:
    ```bash
    pytest tests/                          # All tests
    pytest tests/functional/               # Functional tests only
    pytest tests/integration/              # Integration tests (needs Azure creds)
    ```

13. **Check `docs/KNOWN_LIMITATIONS.md`** for full details on edge cases and workarounds.

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
