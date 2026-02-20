# Known Limitations & Workarounds

This document covers known limitations discovered during end-to-end testing of the CLI wizard migration flow (Scenario #2).

## 1. ARM-to-Data-Plane Propagation Delay

**Issue:** After creating a connection via ARM, the Azure AI Foundry data-plane API may not immediately see it. This can cause a 404 error when creating an agent that references the newly created connection.

**Workaround:** The wizard now waits 15 seconds after connection creation and the agent builder retries up to 3 times with increasing delays (10s, 20s, 30s). In rare cases with high Azure control-plane latency, you may need to re-run the wizard (it will resume from the last step).

## 2. RBAC Prerequisites for Search Integration

**Issue:** The AI Services managed identity must have the correct RBAC roles on the Azure AI Search service. Without these roles, the agent is created successfully but search queries return no results or fail silently.

**Required roles on the Azure AI Search resource:**
- `Search Index Data Reader` — allows the agent to query index data
- `Search Service Contributor` — allows the agent to read index metadata

**How to assign:**
```bash
# Get the AI Services principal ID
PRINCIPAL_ID=$(az cognitiveservices account show \
  --name <ai-services-name> \
  --resource-group <rg> \
  --query identity.principalId -o tsv)

SEARCH_ID=$(az resource show \
  --name <search-service-name> \
  --resource-group <rg> \
  --resource-type Microsoft.Search/searchServices \
  --query id -o tsv)

# Assign roles
az role assignment create --role "Search Index Data Reader" \
  --assignee-object-id $PRINCIPAL_ID --assignee-principal-type ServicePrincipal \
  --scope $SEARCH_ID

az role assignment create --role "Search Service Contributor" \
  --assignee-object-id $PRINCIPAL_ID --assignee-principal-type ServicePrincipal \
  --scope $SEARCH_ID
```

RBAC propagation can take 5–10 minutes after assignment.

## 3. CognitiveServices vs ML Workspace Project Discovery

**Issue:** Azure AI Foundry projects may be provisioned as either `Microsoft.CognitiveServices/accounts` (kind=AIServices/Project) or `Microsoft.MachineLearningServices/workspaces` (kind=Project). The data-plane agent API only works with CognitiveServices-backed projects.

**Workaround:** The tool now discovers projects from both providers and prefers CognitiveServices-backed projects. If only an ML Workspace project is found, the wizard will still proceed but agent creation may fail. In that case, create a CognitiveServices-backed AI Foundry project in the Azure portal.

## 4. Index Name Extraction

**Issue:** OYD configurations embed the search index name inside the data source parameters. If the wizard cannot extract it automatically (e.g., the OYD config uses a non-standard structure), the agent will be created without an index filter, which may cause it to search across all indexes on the connection.

**Workaround:** The wizard now extracts the index name from `parameters.indexName` or `parameters.endpoint` in OYD data sources. If extraction fails, the user is prompted to enter the index name manually during the discovery step.

## 5. Agent Search Tool Invocation

**Issue:** The Foundry agent may not always invoke the Azure AI Search tool even when the user's query is relevant. This depends on the system prompt and the agent's tool-calling behavior.

**Workaround:** Ensure the agent's system prompt (instructions) explicitly tells the agent to search for information using its tools. For example: *"You are a helpful assistant. Use the search tool to find information before answering questions."*

## 6. azure-mgmt-resource Compatibility

**Issue:** `azure-mgmt-resource` version 25.x introduced a breaking change to the `SubscriptionClient` import path, causing an `ImportError` at runtime.

**Workaround:** The dependency is now pinned to `>=23.0.0,<25.0.0` in `pyproject.toml`.
