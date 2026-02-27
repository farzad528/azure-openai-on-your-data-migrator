# OYD-to-Foundry Migration — Complete Findings & Execution Guide

**Date**: February 17, 2026
**Author**: Suresh P (via GitHub Copilot CLI Agent)
**Repository**: `farzad528/azure-openai-on-your-data-migrator`
**Subscription**: `ME-MngEnvMCAP687688-surep-1` (`2588d490-7849-4b98-9b57-8309b012872b`)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Worked](#2-what-worked)
3. [What Did NOT Work](#3-what-did-not-work)
4. [Pre-requisites & Azure Resources](#4-pre-requisites--azure-resources)
5. [Foundry Project vs Hub — Critical Distinction](#5-foundry-project-vs-hub--critical-distinction)
6. [OYD Data Migrator Wizard Assessment](#6-oyd-data-migrator-wizard-assessment)
7. [REST API Script — What Worked](#7-rest-api-script--what-worked)
8. [Step-by-Step Execution Guide](#8-step-by-step-execution-guide)
9. [Verification & Validation](#9-verification--validation)
10. [T-Shirt Sizing & Duration Estimates](#10-t-shirt-sizing--duration-estimates)
11. [Key Learnings](#11-key-learnings)
12. [Bugs Found & Fixed](#12-bugs-found--fixed)
13. [Appendix — API Reference](#13-appendix--api-reference)

---

## 1. Executive Summary

We attempted to migrate an Azure OpenAI "On Your Data" (OYD) configuration to Azure AI Foundry Agent Service using the `oyd-migrator` CLI tool. The **interactive wizard failed** due to 5 bugs and a fundamental incompatibility with non-TTY environments. We then created a **direct REST API migration script** (`scripts/run_migration.py`) that **successfully completed the migration** end-to-end, including side-by-side validation against the original OYD source.

| Aspect | Result |
|--------|--------|
| OYD Wizard (Interactive) | ❌ Did not complete — 5 bugs, TTY dependency |
| REST API Script (Programmatic) | ✅ Fully working — agent created, tested, validated |
| Foundry Agent produces grounded answers | ✅ Equivalent to OYD source |
| All 175 unit/functional tests | ✅ Passing |

---

## 2. What Worked

### ✅ Direct REST API Migration

The programmatic migration via `scripts/run_migration.py` worked flawlessly:

| Step | API Endpoint | Method | Status |
|------|-------------|--------|--------|
| Authentication | `AzureCliCredential` → `https://ai.azure.com/.default` | Token | ✅ |
| Connection lookup | `{project}/connections?api-version=2025-05-01` | GET | ✅ |
| Agent creation | `{project}/assistants?api-version=2025-05-01` | POST | ✅ 200 |
| Thread creation | `{project}/threads?api-version=2025-05-01` | POST | ✅ 200 |
| Message posting | `{project}/threads/{id}/messages?api-version=2025-05-01` | POST | ✅ 200 |
| Run execution | `{project}/threads/{id}/runs?api-version=2025-05-01` | POST | ✅ 200 |
| Run polling | `{project}/threads/{id}/runs/{id}?api-version=2025-05-01` | GET | ✅ completed |
| Response retrieval | `{project}/threads/{id}/messages?api-version=2025-05-01` | GET | ✅ 200 |

### ✅ Foundry Agent Response Quality

All 3 test queries returned correct, grounded answers with citations:

| Query | Foundry Agent Response | OYD Response | Match |
|-------|----------------------|--------------|-------|
| "What is the parental leave policy?" | 16 weeks primary, 6 weeks secondary | 16 weeks primary, 6 weeks secondary | ✅ |
| "How many vacation days do employees get?" | 15 days/year, 1.25/month accrual | 15 days/year, 1.25/month accrual | ✅ |
| "What is the remote work policy?" | Up to 3 days/week, hybrid | Up to 3 days/week, manager approval | ✅ |

### ✅ Search Connection via Azure Portal

Creating the AI Search connection through the Azure AI Foundry **portal UI** worked correctly. The connection was provisioned at:

```
/subscriptions/{sub}/resourceGroups/rg-suresh-8897/providers/Microsoft.CognitiveServices/
accounts/aoai-oyd-migrated-resource/projects/aoai-oyd-migrated/connections/livsrcsvc
```

### ✅ OYD Source (Original) Still Works

The original OYD configuration (inline `data_sources` in chat completions) continues to work:

```
POST https://myaoaidemo.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-10-21
Authorization: Bearer {cognitive_services_token}
Body: { "messages": [...], "data_sources": [{ "type": "azure_search", ... }] }
```

### ✅ Bug Fixes Applied (5 bugs, all fixed)

All 5 bugs found during wizard testing were fixed and all 175 tests pass.

---

## 3. What Did NOT Work

### ❌ Interactive Wizard (`oyd-migrator wizard`)

The CLI wizard uses `questionary` for interactive prompts (arrow-key selection, spinners, Rich console rendering). **This cannot be automated** from:
- GitHub Copilot CLI coding agent terminal
- CI/CD pipelines
- Any non-TTY environment
- Scripted subprocess calls

**Root cause**: `questionary` requires a real TTY device with ANSI escape code support. There is **no `--non-interactive` or `--yes` flag**.

### ❌ Connection Creation via REST API

Programmatic creation of search connections via the Foundry project's REST API returned **405 Method Not Allowed**:

```
PUT  {project}/connections/livsrcsvc?api-version=2025-05-01  → 405
POST {project}/connections?api-version=2025-05-01             → 405
```

**Workaround**: Create the connection manually via Azure AI Foundry portal **before** running the migration script.

**Alternative that works**: Connection creation via Azure Management API with `2025-04-01-preview` version:
```
PUT https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}/providers/
Microsoft.CognitiveServices/accounts/{acct}/connections/{name}?api-version=2025-04-01-preview
```

### ❌ OYD Wizard's Connection Manager Service

The `ConnectionManagerService` class in the tool has two bugs:
1. Uses `AzureScopes.MANAGEMENT` (`https://management.azure.com/.default`) but the Foundry project endpoint requires `https://ai.azure.com/.default`
2. Uses API version `2024-07-01-preview` which newer Foundry accounts don't support

### ❌ DNS Resolution for Older Hub Endpoints

The original target `https://aihub4demo.services.ai.azure.com` returned DNS resolution failure (`getaddrinfo failed`). This is because `aihub4demo` is an **ML Workspace Hub**, not a newer **Foundry Account**. Only newer Foundry Accounts have `*.services.ai.azure.com` DNS records.

### ❌ OYD Discovery Auto-Detection

The wizard's `discover all` command could not auto-detect OYD configurations because OYD is configured **inline** per-request, not as a persistent deployment property. The `/extensions` endpoint doesn't exist.

---

## 4. Pre-requisites & Azure Resources

### Azure Resources That Must Be Pre-Provisioned

| Resource | Type | Purpose | How to Create |
|----------|------|---------|---------------|
| **Azure AI Search service** | `Microsoft.Search/searchServices` | Hosts the search index with your data | Azure Portal → Create AI Search |
| **Search index with data** | Search Index | The actual indexed documents | Portal, REST API, or SDK |
| **Azure AI Foundry account** | `Microsoft.CognitiveServices/accounts` (kind: `AIServices`) | Hosts the Foundry project | Azure Portal → Create AI Foundry |
| **Foundry project** | Foundry Project under the account | Container for agents, connections | Azure AI Foundry portal |
| **Model deployment** | OpenAI model in the Foundry project | The LLM for the agent (e.g., `gpt-4o-mini`) | Foundry portal → Models → Deploy |
| **Search connection** | Project connection to AI Search | Links the agent to the search index | Foundry portal → Settings → Connections |

### Authentication Requirements

| Credential | Scope | When Used |
|------------|-------|-----------|
| Azure CLI (`az login`) | — | All operations |
| `https://ai.azure.com/.default` | Foundry Agent Service APIs | Agent CRUD, threads, runs |
| `https://cognitiveservices.azure.com/.default` | AOAI chat completions | OYD queries (original source) |
| `https://management.azure.com/.default` | ARM API | Resource discovery, connection creation via ARM |

### RBAC Roles Required

| Role | Scope | Purpose |
|------|-------|---------|
| `Cognitive Services OpenAI User` | AOAI resource | OYD chat completion queries |
| `Azure AI Developer` | Foundry project | Create agents, threads, runs |
| `Search Index Data Reader` | Search service | Read search index data |
| `Contributor` or `Owner` | Resource group | Create connections (if via ARM) |

### Software Prerequisites

```bash
# Python 3.10+
python --version

# Azure CLI authenticated
az login
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Install the migrator tool
cd azure-openai-on-your-data-migrator
pip install -e .

# Or just use the REST script (minimal deps)
pip install azure-identity requests rich
```

---

## 5. Foundry Project vs Hub — Critical Distinction

### ⚠️ This migration ONLY works with Foundry Projects, NOT Hubs

| Attribute | Foundry Project (✅ Works) | ML Workspace Hub (❌ Doesn't Work) |
|-----------|--------------------------|-------------------------------------|
| **Resource type** | `Microsoft.CognitiveServices/accounts` (kind: `AIServices`) | `Microsoft.MachineLearningServices/workspaces` (kind: `Hub`) |
| **Endpoint format** | `https://{name}.services.ai.azure.com/api/projects/{project}` | `https://{name}.services.ai.azure.com` (may not resolve) |
| **DNS resolution** | ✅ `*.services.ai.azure.com` resolves | ❌ May fail with `getaddrinfo` error |
| **Agents API** | ✅ `{project}/assistants?api-version=2025-05-01` returns 200 | ❌ API not available |
| **Connections API** | ✅ `{project}/connections?api-version=2025-05-01` returns 200 | ❌ Returns 400 or 405 |
| **Created via** | Azure AI Foundry portal (newer) | Azure ML Studio (older) |

### How to Identify Your Resource Type

```bash
# Check if it's a CognitiveServices account (Foundry)
az cognitiveservices account show -n YOUR_RESOURCE_NAME -g YOUR_RG --query "kind"

# Expected output for Foundry: "AIServices"
# If it shows nothing or errors, it's likely an ML Workspace Hub
```

### Our Experience

| Resource | Type | Endpoint | DNS | Agent API |
|----------|------|----------|-----|-----------|
| `aihub4demo` | ML Workspace Hub | `aihub4demo.services.ai.azure.com` | ❌ Failed | N/A |
| `aoai-oyd-migrated-resource` | AIServices (Foundry) | `aoai-oyd-migrated-resource.services.ai.azure.com` | ✅ Resolved | ✅ Working |

### Recommendation

**Always create a new Azure AI Foundry resource** (not an ML Hub) for migration targets. Use the Azure AI Foundry portal at https://ai.azure.com to create projects — this ensures you get the newer resource type with working DNS and API support.

---

## 6. OYD Data Migrator Wizard Assessment

### Wizard Status: ❌ NOT Recommended for Production Use

The `oyd-migrator wizard` interactive CLI has significant issues that prevent it from completing a migration:

| Stage | Status | Issue |
|-------|--------|-------|
| 1. Authentication | ✅ Works | Azure CLI credential detected correctly |
| 2. Discovery | ⚠️ Partial | Finds search indexes but misses OYD configs (Bug #1) |
| 3. Configuration | ⚠️ Partial | Manual AOAI entry doesn't collect OYD details (Bug #2) |
| 4. Migration | ❌ Fails | Connection manager uses wrong auth scope; API version mismatch |
| 5. Validation | ❌ Not reached | Never gets past Stage 4 |

### Bugs Found (5 Total)

| # | Bug | Severity | Impact |
|---|-----|----------|--------|
| 1 | `/extensions` endpoint returns 404 | **Critical** | Discovery never finds OYD configs |
| 2 | Manual AOAI entry skips OYD source details | **High** | Migration has no search index info |
| 3 | `disableLocalAuth` crashes key retrieval | **Medium** | Can't inventory search indexes |
| 4 | `--config` flag doesn't skip stages | **Medium** | YAML config doesn't accelerate wizard |
| 5 | Session resume doesn't validate credentials | **Low** | Resumed sessions may fail with expired tokens |

### Root Cause: TTY Dependency

The wizard uses `questionary` for interactive prompts (arrow-key selection, checkboxes, confirmations). This library requires a **real terminal (TTY)** and cannot be driven from:
- Coding agents (GitHub Copilot CLI, Claude Code, etc.)
- CI/CD pipelines (GitHub Actions, Azure DevOps)
- Subprocess automation (`subprocess.run()`)
- Any environment without ANSI escape code support

**No `--non-interactive` or `--yes` flag exists** in the current codebase.

---

## 7. REST API Script — What Worked

### The Solution: `scripts/run_migration.py`

A self-contained Python script that calls the Foundry Agent Service REST APIs directly, bypassing the wizard entirely.

### Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│   OYD Source        │     │  Migration Script    │     │  Foundry Agent   │
│   (myaoaidemo)      │     │  (run_migration.py)  │     │  Service         │
│                     │     │                      │     │                  │
│ ┌─────────────────┐ │     │  1. Authenticate     │     │ ┌──────────────┐ │
│ │ gpt-4o-mini     │─┼─────┤  2. Lookup connection│─────┤ │ hr-policy-   │ │
│ │ + data_sources  │ │     │  3. Create agent     │     │ │ agent        │ │
│ └─────────────────┘ │     │  4. Test & compare   │     │ │ + AI Search  │ │
│                     │     │                      │     │ └──────────────┘ │
│ ┌─────────────────┐ │     └──────────────────────┘     │                  │
│ │ livsrcsvc       │ │                                   │ ┌──────────────┐ │
│ │ hr-policies-idx │─┼───────────────────────────────────┤ │ livsrcsvc    │ │
│ └─────────────────┘ │                                   │ │ connection   │ │
└─────────────────────┘                                   │ └──────────────┘ │
                                                          └──────────────────┘
```

### Key Design Decisions

| Decision | Why |
|----------|-----|
| Direct REST calls (not SDK) | SDK classes use wrong auth scopes and old API versions |
| Auth scope `https://ai.azure.com/.default` | Required by newer Foundry account endpoints |
| API version `2025-05-01` | Oldest version supported by new Foundry accounts |
| Connection created via portal | REST API returns 405 for connection creation on project endpoint |
| Side-by-side OYD comparison | Validates migration fidelity automatically |

### Token Scopes

```python
# For Foundry Agent Service (agents, threads, runs)
token = credential.get_token("https://ai.azure.com/.default")

# For OYD queries (chat completions on AOAI)
token = credential.get_token("https://cognitiveservices.azure.com/.default")

# For Azure Resource Manager (resource discovery, ARM-based connection creation)
token = credential.get_token("https://management.azure.com/.default")
```

---

## 8. Step-by-Step Execution Guide

### Phase 1: Prepare Azure Resources (Portal)

#### Step 1.1: Verify Source OYD Configuration

Confirm your OYD source works by calling the chat completions API:

```bash
# Get a token
TOKEN=$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)

# Test OYD call
curl -X POST "https://YOUR_AOAI_RESOURCE.openai.azure.com/openai/deployments/YOUR_DEPLOYMENT/chat/completions?api-version=2024-10-21" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "test query"}],
    "data_sources": [{
      "type": "azure_search",
      "parameters": {
        "endpoint": "https://YOUR_SEARCH.search.windows.net",
        "index_name": "YOUR_INDEX",
        "authentication": {"type": "api_key", "key": "YOUR_SEARCH_KEY"},
        "query_type": "semantic",
        "semantic_configuration": "YOUR_SEMANTIC_CONFIG"
      }
    }]
  }'
```

#### Step 1.2: Create Foundry Project

1. Go to https://ai.azure.com
2. Click **+ Create project**
3. Select or create a new **AI Foundry resource** (NOT an ML Hub)
4. Choose a region (ideally same as your search service)
5. Complete creation

#### Step 1.3: Deploy a Model

1. In your Foundry project, go to **Models + endpoints** → **Deploy model**
2. Deploy `gpt-4o-mini` (or `gpt-4o`, `gpt-4.1`)
3. Note the deployment name (e.g., `gpt-4o-mini`)

#### Step 1.4: Create Search Connection

1. In your Foundry project, go to **Management** → **Connected resources**
2. Click **+ New connection** → **Azure AI Search**
3. Select your search service
4. Choose authentication: **API Key** or **Microsoft Entra ID**
5. Save and note the connection name

#### Step 1.5: Note Your Endpoint

Your project endpoint follows this format:
```
https://{foundry-resource-name}.services.ai.azure.com/api/projects/{project-name}
```

Verify it resolves:
```bash
curl -s -o /dev/null -w "%{http_code}" https://YOUR-RESOURCE.services.ai.azure.com
# Should return 200
```

### Phase 2: Configure the Script

#### Step 2.1: Clone and Install

```bash
git clone https://github.com/farzad528/azure-openai-on-your-data-migrator.git
cd azure-openai-on-your-data-migrator
pip install -e .
# Or minimal deps: pip install azure-identity requests rich
```

#### Step 2.2: Edit Configuration

Open `scripts/run_migration.py` and update the configuration section:

```python
# Foundry project endpoint
PROJECT_ENDPOINT = "https://YOUR-RESOURCE.services.ai.azure.com/api/projects/YOUR-PROJECT"

# Model deployment name (must match what you deployed in Step 1.3)
MODEL = "gpt-4o-mini"

# Search connection name (must match what you created in Step 1.4)
SEARCH_CONNECTION_NAME = "your-search-connection"

# Search index name
SEARCH_INDEX_NAME = "your-index-name"

# Search query type: simple, semantic, vector, vector_semantic_hybrid
SEARCH_QUERY_TYPE = "semantic"

# Agent name (your choice)
AGENT_NAME = "my-migrated-agent"

# Agent instructions (migrate your OYD system message here)
AGENT_INSTRUCTIONS = "Your system message..."

# (Optional) OYD source for comparison
OYD_ENDPOINT = "https://your-aoai.openai.azure.com"
OYD_DEPLOYMENT = "your-deployment"
OYD_SEARCH_KEY = "your-search-api-key"
```

### Phase 3: Execute Migration

```bash
# Authenticate
az login
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Run the migration
cd azure-openai-on-your-data-migrator
python scripts/run_migration.py
```

### Phase 4: Expected Output

```
╭── Migration Script ──╮
│ OYD-to-Foundry Programmatic Migration │
╰──────────────────────╯

◐ Authenticating with Azure CLI...
✓ Authentication successful.

◐ Looking up search connection...
✓ Connection found: livsrcsvc
  ID: /subscriptions/.../connections/livsrcsvc

◐ Creating Foundry agent...
✓ Agent created: hr-policy-agent
  ID: asst_AFHKe1Fa4wwM2ytB5cCwbjfE
  Model: gpt-4o-mini

◐ Testing migrated agent...

┌─────────────────┬──────────────────┬───────┬──────────────────┬───────┬───────┐
│ Query           │ Foundry Response │ Cites │ OYD Response     │ Cites │ Match │
├─────────────────┼──────────────────┼───────┼──────────────────┼───────┼───────┤
│ Parental leave? │ 16 weeks primary │   1   │ 16 weeks primary │   3   │   ✓   │
│ Vacation days?  │ 15 days/year     │   1   │ 15 days/year     │   5   │   ✓   │
│ Remote work?    │ 3 days/week      │   1   │ 3 days/week      │   4   │   ✓   │
└─────────────────┴──────────────────┴───────┴──────────────────┴───────┴───────┘

╭── Migration Result ──╮
│ ✓ Migration complete! │
╰──────────────────────╯
```

---

## 9. Verification & Validation

### Automated Verification (Built into Script)

The script automatically:
1. Creates the agent
2. Sends test queries to the Foundry agent
3. Sends the **same queries** to the original OYD source
4. Compares responses side-by-side in a Rich table
5. Reports ✓ or ✗ match status

### Manual Verification Steps

#### 9.1. Azure AI Foundry Portal

1. Navigate to https://ai.azure.com
2. Select your project
3. Go to **Agents** section
4. Find your agent (e.g., `hr-policy-agent`)
5. Open the **Playground**
6. Send test queries and verify grounded answers with citations

#### 9.2. REST API Verification

```bash
# List agents in the project
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

curl "https://YOUR-RESOURCE.services.ai.azure.com/api/projects/YOUR-PROJECT/assistants?api-version=2025-05-01" \
  -H "Authorization: Bearer $TOKEN"
```

#### 9.3. Checklist

| Check | How | Expected |
|-------|-----|----------|
| Agent exists | List assistants API | Agent ID returned |
| Agent has search tool | Get assistant details | `tools: [{type: "azure_ai_search"}]` |
| Agent uses correct index | Check `tool_resources` | `index_name` matches |
| Agent returns grounded answers | Send test query via thread/run | Response contains citations |
| Response quality matches OYD | Compare side-by-side | Same key facts present |
| No hallucination | Ask about data NOT in index | Agent says "I don't have information" |

#### 9.4. Negative Test

Ask the agent a question that is NOT in your search index:
```
"What is the company's Mars colonization policy?"
```

Expected: Agent should respond that it cannot find relevant information (not hallucinate).

---

## 10. T-Shirt Sizing & Duration Estimates

### Per-Deployment Migration

| Phase | Tasks | Duration | Size |
|-------|-------|----------|------|
| **Setup** | Create Foundry project, deploy model, create connection | 15-30 min | S |
| **Configuration** | Edit `run_migration.py` with source/target details | 5-10 min | XS |
| **Execution** | Run the script | 2-5 min | XS |
| **Validation** | Verify agent works, compare with OYD | 10-15 min | S |
| **Cleanup** | Decommission OYD source (after validation period) | 5 min | XS |
| **Total per deployment** | | **40-65 min** | **S** |

### Batch Migration (Multiple Deployments)

| Scale | Deployments | Duration | Size | Notes |
|-------|-------------|----------|------|-------|
| **XS** | 1-5 | 1-3 hours | XS | Manual, one-by-one |
| **S** | 5-20 | 1-2 days | S | Script per deployment |
| **M** | 20-100 | 3-5 days | M | Parameterized script, batch execution |
| **L** | 100-1,000 | 1-3 weeks | L | Need automation framework, parallel execution |
| **XL** | 1,000-20,000 | 4-8 weeks | XL | Need orchestration, rollback, monitoring |

### For the 20K+ CCID Target (from OYD Deprecation)

| Phase | Duration | Team Size |
|-------|----------|-----------|
| Tooling & automation | 1-2 weeks | 2-3 engineers |
| Pilot batch (100 CCIDs) | 1 week | 2 engineers |
| Main migration (20K CCIDs) | 4-6 weeks | 3-5 engineers |
| Validation & cleanup | 2 weeks | 2 engineers |
| **Total** | **8-11 weeks** | **3-5 engineers** |

### Key Duration Factors

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Foundry project creation | 15 min per project | Batch via ARM templates |
| Model deployment | 5 min per deployment | Can reuse across agents |
| Connection creation | Must be done in portal currently | ARM API with `2025-04-01-preview` |
| Agent creation | ~2 seconds per agent (API call) | Highly parallelizable |
| Validation | 30-60 seconds per agent (thread + run) | Automated in script |
| Semantic config mapping | Manual if configs vary | Template per query type |
| Strictness mapping | No direct equivalent in Foundry | `top_k` adjustment or `reranker_score_threshold` |

---

## 11. Key Learnings

### L1: OYD is NOT a Deployment Property

**Learning**: OYD configuration is specified **inline** in each chat completion request via the `data_sources` parameter. There is no Azure API that stores or returns OYD configuration for a deployment. This means:
- Auto-discovery of OYD configurations is **fundamentally impossible** via APIs
- The source of truth is the **application code** that makes OYD calls
- Customers must **know** their OYD configuration details upfront

### L2: Foundry Account ≠ ML Workspace Hub

**Learning**: Newer Azure AI Foundry resources (`Microsoft.CognitiveServices/accounts` with kind `AIServices`) have working DNS at `*.services.ai.azure.com`. Older ML Workspace Hubs (`Microsoft.MachineLearningServices/workspaces` with kind `Hub`) may **not resolve** at the same domain.

**Impact**: Always create new Foundry resources via https://ai.azure.com, not via the legacy Azure ML Studio.

### L3: API Versions Matter — A Lot

**Learning**: Different Foundry resources support different API versions:

| API | Old Foundry | New Foundry |
|-----|-------------|-------------|
| Connections (list) | `2024-07-01-preview` | `2025-05-01` |
| Connections (create via ARM) | `2024-10-01` | `2025-04-01-preview` |
| Agents (assistants) | `v1` | `2025-05-01` |
| Connections (create via project) | N/A | ❌ 405 (not supported) |

### L4: Auth Scopes Are Endpoint-Specific

**Learning**: Different endpoints require different OAuth scopes:

| Endpoint | Required Scope |
|----------|---------------|
| `*.services.ai.azure.com` (Foundry) | `https://ai.azure.com/.default` |
| `*.openai.azure.com` (AOAI) | `https://cognitiveservices.azure.com/.default` |
| `management.azure.com` (ARM) | `https://management.azure.com/.default` |
| `*.search.windows.net` (AI Search) | `https://search.azure.com/.default` |

Using the wrong scope returns 401 with the message: `"audience is incorrect (https://ai.azure.com)"`.

### L5: Connection Creation Only Works via Portal or ARM

**Learning**: Creating connections via the Foundry project data-plane REST API (`{project}/connections`) returns 405 Method Not Allowed. Connections must be created either:
1. **Azure AI Foundry portal** (recommended for manual migrations)
2. **ARM API** with `2025-04-01-preview` version (for automated migrations)

### L6: Interactive Wizard is TTY-Dependent

**Learning**: The `questionary` library used for interactive prompts requires a real terminal. This makes the wizard unusable from coding agents, CI/CD, or any non-interactive environment. A `--non-interactive` mode should be added to the CLI.

### L7: Strictness Has No Direct Equivalent

**Learning**: OYD's `strictness` parameter (1-5) controls how strictly the model follows search results. Foundry Agent Service with AI Search Tool has no direct equivalent. Mapping options:
- **Search Tool**: Use `top_k` (lower = stricter) and post-processing filters
- **Knowledge Base**: Use `reranker_score_threshold` (formula: `(strictness - 1) * 1.0`)

### L8: Citation Format Changes

**Learning**: OYD returns `context.citations` with structured fields (`title`, `content`, `url`, `chunk_id`). Foundry Agent returns `annotations` with `url_citation` type and different structure. Client code consuming citations needs to be updated.

### L9: `disableLocalAuth` Requires Bearer Token

**Learning**: If the AOAI or Search resource has `disableLocalAuth: true`, API key authentication is disabled. The tool must detect this and use bearer token authentication instead. This affected both search index inventory and OYD discovery.

### L10: Session Management Needs Credential Validation

**Learning**: When resuming a saved wizard session, the original Azure credentials may have expired. The tool should validate credential freshness on resume and prompt for re-authentication if needed.

---

## 12. Bugs Found & Fixed

### Summary Table

| # | Bug | Severity | Root Cause | Fix Location | Lines Changed |
|---|-----|----------|------------|--------------|---------------|
| 1 | `/extensions` endpoint returns 404 | **Critical** | OYD is inline, not a deployment property | `aoai_discovery.py` | +38 / −20 |
| 2 | Manual entry skips OYD source details | **High** | UI only collects resource name, not search config | `discovery_wizard.py` | +135 / −7 |
| 3 | `disableLocalAuth` crashes key retrieval | **Medium** | No check for `disableLocalAuth` flag | `search_inventory.py`, `aoai_discovery.py` | +19 / −9 |
| 4 | `--config` doesn't skip stages | **Medium** | No stage-skip logic after YAML load | `migrate.py` | +9 / −2 |
| 5 | Session resume ignores expired tokens | **Low** | No credential validation on resume | `migrate.py` | +10 / −0 |

### Files Modified

| File | Bugs Fixed | Changes |
|------|-----------|---------|
| `oyd_migrator/services/aoai_discovery.py` | #1, #3 | Chat-capable fallback, `disableLocalAuth` detection |
| `oyd_migrator/cli/wizards/discovery_wizard.py` | #2 | Full OYD config collection in manual entry |
| `oyd_migrator/cli/commands/migrate.py` | #4, #5 | Config stage-skip, credential validation |
| `oyd_migrator/services/search_inventory.py` | #3 | Bearer token for `disableLocalAuth` |
| `oyd_migrator/services/auth.py` | — | Import fix + credential timeout |
| `pyproject.toml` | — | Added test dependencies |

**Total**: 6 files modified, +225 / −37 lines

### Bug Fix Details

See [`docs/OYD-Migrator-Fixes-and-Tests-Contribution-Guide.md`](OYD-Migrator-Fixes-and-Tests-Contribution-Guide.md) for complete per-bug analysis with code diffs.

---

## 13. Appendix — API Reference

### A. Foundry Agent Service APIs (api-version=2025-05-01)

**Base URL**: `https://{resource}.services.ai.azure.com/api/projects/{project}`
**Auth**: `Bearer` token with scope `https://ai.azure.com/.default`

| Operation | Method | Path | Request Body |
|-----------|--------|------|-------------|
| List connections | GET | `/connections` | — |
| List agents | GET | `/assistants` | — |
| Create agent | POST | `/assistants` | `{name, model, instructions, tools, tool_resources}` |
| Create thread | POST | `/threads` | `{}` |
| Add message | POST | `/threads/{id}/messages` | `{role: "user", content: "..."}` |
| Run agent | POST | `/threads/{id}/runs` | `{assistant_id: "asst_..."}` |
| Poll run | GET | `/threads/{id}/runs/{id}` | — |
| Get messages | GET | `/threads/{id}/messages` | — |

### B. Agent Creation Body (Search Tool)

```json
{
    "name": "my-agent",
    "model": "gpt-4o-mini",
    "instructions": "Your system message...",
    "tools": [{"type": "azure_ai_search"}],
    "tool_resources": {
        "azure_ai_search": {
            "indexes": [{
                "index_connection_id": "/subscriptions/.../connections/my-search",
                "index_name": "my-index",
                "query_type": "semantic",
                "top_k": 5
            }]
        }
    }
}
```

### C. OYD Chat Completion Body (Original Source)

```json
{
    "messages": [{"role": "user", "content": "Your query"}],
    "data_sources": [{
        "type": "azure_search",
        "parameters": {
            "endpoint": "https://your-search.search.windows.net",
            "index_name": "your-index",
            "authentication": {
                "type": "api_key",
                "key": "your-search-key"
            },
            "query_type": "semantic",
            "semantic_configuration": "your-semantic-config"
        }
    }]
}
```

### D. Connection Creation via ARM API

```bash
# Only needed if creating connections programmatically (not via portal)
PUT https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}/providers/
    Microsoft.CognitiveServices/accounts/{account}/connections/{name}
    ?api-version=2025-04-01-preview

Body:
{
    "name": "my-search-connection",
    "properties": {
        "category": "CognitiveSearch",
        "target": "https://your-search.search.windows.net",
        "authType": "ApiKey",
        "credentials": {"key": "your-api-key"}
    }
}
```

### E. Query Type Mapping (OYD → Foundry)

| OYD `query_type` | Foundry Agent `query_type` | Notes |
|-------------------|----------------------------|-------|
| `simple` | `simple` | Basic keyword search |
| `semantic` | `semantic` | Requires semantic configuration on the index |
| `vector` | `vector` | Requires vector fields in the index |
| `vector_simple_hybrid` | `vector_simple_hybrid` | Combined keyword + vector |
| `vector_semantic_hybrid` | `vector_semantic_hybrid` | Full hybrid with reranking |

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-17 | 1.0 | Initial document — complete findings from live migration |
