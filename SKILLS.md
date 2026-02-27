# Skills Reference

This document provides guidance for both **coding agents** (GitHub Copilot, Claude Code, etc.)
and **human operators** performing OYD-to-Foundry migrations. It covers when to use each
migration path, how to execute each one, and SDK references for integration work.

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

# 3. Confirm search index exists
az search index show --service-name <your-search-service> --name <index-name> --resource-group <rg>

# 4. Confirm Foundry project endpoint resolves
# Must be a CognitiveServices/AIServices account, NOT an ML Workspace Hub
az cognitiveservices account show --name <your-foundry-resource> --resource-group <rg> --query "kind"
# Expected output: "AIServices"

# 5. Confirm model is deployed in the Foundry project
az cognitiveservices account deployment show --name <your-foundry-resource> --resource-group <rg> --deployment-name gpt-4o-mini
```

**Required Azure resources (must be pre-provisioned):**

| Resource | Type | Notes |
|----------|------|-------|
| Azure AI Search service | `Microsoft.Search/searchServices` | With indexed data |
| Foundry account | `Microsoft.CognitiveServices/accounts` (kind: `AIServices`) | NOT an ML Workspace Hub |
| Foundry project | Project under the Foundry account | |
| Model deployment | `gpt-4o-mini` or `gpt-4o` in the project | |
| Search connection | Connected resource in the Foundry project | Create via portal before running script |

**RBAC roles required:**

| Role | Scope |
|------|-------|
| `Cognitive Services OpenAI User` | AOAI resource (for OYD validation queries) |
| `Azure AI Developer` | Foundry project (for agent CRUD) |
| `Search Index Data Reader` | Search service (for agent to query index) |
| `Search Service Contributor` | Search service (for index metadata) |

### How to Create the Search Connection (Portal — Required Before Script)

The REST API does not support creating connections via the project data-plane endpoint.
Create it manually once in the portal:

1. Go to https://ai.azure.com → select your project
2. **Management** → **Connected resources** → **+ New connection**
3. Select **Azure AI Search** → choose your search service
4. Set auth to **API Key** or **Microsoft Entra ID**
5. Note the connection name (use this as `SEARCH_CONNECTION_NAME` in the script)

### Execute the Migration

```bash
# Clone and install
git clone https://github.com/farzad528/azure-openai-on-your-data-migrator.git
cd azure-openai-on-your-data-migrator
pip install -e .

# Edit configuration (open in editor)
# scripts/run_migration.py — update the CONFIG section at the top

# Run
python scripts/run_migration.py
```

### Configuration Reference (`scripts/run_migration.py`)

```python
PROJECT_ENDPOINT  = "https://<foundry-resource>.services.ai.azure.com/api/projects/<project-name>"
MODEL             = "gpt-4o-mini"          # Must match a deployed model in the project
SEARCH_CONNECTION_NAME = "my-search"       # Connection name created in portal (Step above)
SEARCH_INDEX_NAME = "my-index"             # Azure AI Search index name
SEARCH_QUERY_TYPE = "semantic"             # simple | semantic | vector | vector_semantic_hybrid
AGENT_NAME        = "my-migrated-agent"
AGENT_INSTRUCTIONS = "Your system message / instructions..."
```

### Key API Facts for Coding Agents

```python
# ✅ Correct token scope for Foundry Agent Service
token = credential.get_token("https://ai.azure.com/.default")

# ✅ Correct API version for newer Foundry accounts (CognitiveServices/AIServices)
API_VERSION = "2025-05-01"

# ✅ Correct endpoint format
# https://{resource-name}.services.ai.azure.com/api/projects/{project-name}

# ❌ Wrong — old API version (returns 400 on newer accounts)
# API_VERSION = "2024-07-01-preview"

# ❌ Wrong — ML scope (returns 401 with "audience is incorrect")
# token = credential.get_token("https://management.azure.com/.default")
```

### Verify Success

After the script completes, verify the migrated agent:

```bash
# Get token
$TOKEN = az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv

# List agents in the project
curl "https://<foundry-resource>.services.ai.azure.com/api/projects/<project>/assistants?api-version=2025-05-01" `
  -H "Authorization: Bearer $TOKEN"

# Test with a query (PowerShell)
$body = @{
  role = "user"
  content = "Test query about your data"
} | ConvertTo-Json

# Or open the portal playground:
# https://ai.azure.com → your project → Agents → your agent → Playground
```

---

## Path 2 — Human Wizard (Interactive CLI)

Use this path when a human operator is running the migration interactively in a terminal.

### Prerequisites

```bash
pip install -e .
az login
az account set --subscription "<subscription-id>"
```

### Run the Wizard

```bash
# Full interactive wizard (recommended for first migration)
oyd-migrator wizard

# Or: discover resources first, then migrate
oyd-migrator discover all --resource-group <rg>
oyd-migrator migrate interactive

# Resume a saved session
oyd-migrator migrate sessions
oyd-migrator migrate interactive --resume <session-id>

# Skip to a known config via YAML
oyd-migrator migrate interactive --config migration.yaml
```

### Wizard Stage Overview

| Stage | What Happens | Common Issues |
|-------|-------------|---------------|
| 1. Auth | Detects Azure CLI credentials | Run `az login` if prompted |
| 2. Discovery | Finds AOAI resources and search indexes | OYD config is inline — manual entry may be needed |
| 3. Configuration | Maps OYD → Foundry settings | Select migration path: Search Tool or Knowledge Base |
| 4. Migration | Creates connections and agent | ARM propagation delay (15s wait built in) |
| 5. Validation | Tests agent with sample queries | Verify grounded answers with citations |

### Known Limitations (Wizard)

See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) for full details. Key points:

- **OYD auto-discovery is limited** — OYD config is specified inline per-request (in `data_sources`),
  not stored as a deployment property. The wizard will present all chat-capable deployments as
  candidates and ask you to confirm or enter config details manually.
- **ARM propagation delay** — After connection creation, wait ~15s before agent creation.
  The wizard handles this automatically with retries.
- **RBAC must be assigned first** — The Foundry AI Services managed identity needs
  `Search Index Data Reader` and `Search Service Contributor` on the search resource.
- **Foundry Project type matters** — Only `CognitiveServices/AIServices` projects work.
  ML Workspace Hubs are not supported for agent creation.

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

3. **Create the search connection via portal before running the script** — REST connection
   creation on the project data-plane returns 405. Use the portal or ARM API
   (`api-version=2025-04-01-preview`) instead.

4. **Use the correct token scope** — `https://ai.azure.com/.default`, not management or
   cognitive services scope, for all Foundry Agent Service API calls.

5. **Validate side-by-side** — The script automatically queries both the original OYD source
   and the new Foundry agent with the same queries and compares results.

6. **Check `docs/OYD-Migration-Findings-and-Execution-Guide.md`** for full learnings from
   live end-to-end testing including what worked, what failed, and why.

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

