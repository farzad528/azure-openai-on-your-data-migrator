# OYD Migrator

CLI tool for migrating [Azure OpenAI "On Your Data" (OYD)](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/use-your-data?view=foundry-classic&WT.mc_id=m365-94501-dwahlin&tabs=ai-search%2Ccopilot#what-is-azure-openai-on-your-data) to [Microsoft Foundry Agent Service](https://learn.microsoft.com/azure/ai-foundry/agents) (fka. Azure AI Agent Service).

## Why Migrate?

Azure OpenAI OYD is being deprecated as GPT-4 family models retire (2025). The feature does not support GPT-5 models and is no longer under active development. This tool provides two migration paths:

- **[Azure AI Search](https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search?tabs=indexing%2Cquickstarts) Tool** — Direct index connection for simple RAG
- **[Foundry IQ](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/foundry-iq-connect?view=foundry&tabs=foundry%2Cpython) Knowledge Base** — The knowledge layer built on Azure AI Search agentic retrieval APIs (`/knowledgebases`), for advanced reasoning

## Prerequisites

| Requirement | Description |
|-------------|-------------|
| Python 3.10+ | Required runtime |
| Azure CLI | Run `az login` to authenticate |
| Azure Subscription | With OYD already configured |

### Required Information

| Resource | Location |
|----------|----------|
| **Subscription ID** | Azure Portal → Subscriptions |
| **Azure OpenAI Resource Name** | Azure Portal → Azure OpenAI |
| **Resource Group** | Azure Portal → Azure OpenAI → Overview |
| **Deployment Name** | Azure OpenAI Studio → Deployments |
| **Azure AI Search Service Name** | Azure Portal → Azure AI Search |
| **Search Index Name** | Azure AI Search → Indexes |

### Required RBAC Roles

For **System Assigned Managed Identity** (recommended):

| Role | Assignee | Resource |
|------|----------|----------|
| Search Index Data Reader | Azure OpenAI | Azure AI Search |
| Search Service Contributor | Azure OpenAI | Azure AI Search |
| Storage Blob Data Contributor | Azure OpenAI | Storage Account |
| Cognitive Services OpenAI Contributor | Azure AI Search | Azure OpenAI + Foundry Project |
| Storage Blob Data Reader | Azure AI Search | Storage Account |
| Cognitive Services OpenAI User | Your identity/Web app | Azure OpenAI |

See [RBAC Setup Guide](docs/RBAC.md) for details.

## Quick Start

```bash
pip install -e .
az login
oyd-migrator wizard
```

## Commands

```bash
# Discovery
oyd-migrator discover all -g <resource-group>
oyd-migrator discover aoai -g <resource-group>
oyd-migrator discover indexes --service <name>

# Migration
oyd-migrator wizard
oyd-migrator migrate interactive
oyd-migrator compare

# Validation
oyd-migrator validate agent <name> --project-endpoint <url>
oyd-migrator validate roles -g <resource-group>

# Code generation
oyd-migrator generate python <name> --project-endpoint <url>
```

## Troubleshooting

### 403 Error: Azure Search Access Denied

Verify RBAC configuration:
```bash
oyd-migrator validate roles -g <your-resource-group>
```

### Slow Discovery

Filter by resource group:
```bash
oyd-migrator discover all -g <your-resource-group>
```

## Resources

- [Feature Comparison](FEATURE_COMPARISON.md)
- [Migration Guide](docs/MIGRATION_GUIDE.md)
- [RBAC Setup Guide](docs/RBAC.md)
- [Azure SDK Skills Reference](SKILLS.md)
- [Coding Agent Guide](AGENTS.md)
- [Azure OpenAI On Your Data](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/use-your-data?view=foundry-classic&WT.mc_id=m365-94501-dwahlin&tabs=ai-search%2Ccopilot#what-is-azure-openai-on-your-data)
- [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search?tabs=indexing%2Cquickstarts)
- [Microsoft Foundry Agent Service](https://learn.microsoft.com/azure/ai-foundry/agents)
- [Foundry IQ Knowledge Base](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/foundry-iq-connect?view=foundry&tabs=foundry%2Cpython)

## License

MIT
