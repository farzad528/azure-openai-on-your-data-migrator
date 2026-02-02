# OYD Migrator

CLI tool for migrating Azure OpenAI "On Your Data" (OYD) to Azure AI Foundry Agent Service.

## Why Migrate?

Azure OpenAI OYD is being deprecated as GPT-4 family models retire (2025). The feature does not support GPT-5 models and is no longer under active development. This tool helps you migrate to Foundry Agent Service with two options:

- **Azure AI Search Tool** - Direct index connection for simple RAG
- **Foundry IQ Knowledge Base** - MCP-based for advanced reasoning

## Before You Begin

### Prerequisites

| Requirement | Description |
|-------------|-------------|
| Python 3.10+ | Required for running the tool |
| Azure CLI | Run `az login` to authenticate |
| Azure Subscription | With OYD already configured |

### Required Information

Have the following information ready before starting the migration:

| Resource | How to Find It |
|----------|---------------|
| **Subscription ID** | Azure Portal → Subscriptions |
| **Azure OpenAI Resource Name** | Azure Portal → Azure OpenAI → Your resource name |
| **Resource Group** | Azure Portal → Azure OpenAI → Overview → Resource group |
| **Deployment Name** | Azure OpenAI Studio → Deployments |
| **Azure AI Search Service Name** | Azure Portal → Azure AI Search → Your service name |
| **Search Index Name** | Azure AI Search → Indexes |

### Required RBAC Permissions

If using **System Assigned Managed Identity** (recommended), ensure these role assignments are configured:

| Role | Assignee | Resource |
|------|----------|----------|
| Search Index Data Reader | Azure OpenAI | Azure AI Search |
| Search Service Contributor | Azure OpenAI | Azure AI Search |
| Storage Blob Data Contributor | Azure OpenAI | Storage Account |
| Cognitive Services OpenAI Contributor | Azure AI Search | Azure OpenAI + Foundry Project |
| Storage Blob Data Reader | Azure AI Search | Storage Account |
| Cognitive Services OpenAI User | Your identity/Web app | Azure OpenAI |

See [RBAC Setup Guide](docs/RBAC.md) for detailed instructions.

## Quick Start

```bash
# Install
pip install -e .

# Run interactive wizard
oyd-migrator wizard
```

## Commands

```bash
# Discovery (use filters for faster scanning)
oyd-migrator discover all -g <resource-group>   # Filter by resource group (faster)
oyd-migrator discover aoai -g <resource-group>  # Discover AOAI resources only
oyd-migrator discover indexes --service <name>  # Discover indexes on specific service

# Migration
oyd-migrator wizard                              # Interactive migration wizard
oyd-migrator migrate interactive                 # Start migration wizard
oyd-migrator compare                             # View feature comparison matrix

# Validation
oyd-migrator validate agent <name> --project-endpoint <url>
oyd-migrator validate roles -g <resource-group> # Check RBAC permissions

# Code generation
oyd-migrator generate python <name> --project-endpoint <url>
```

## Authentication

```bash
az login
oyd-migrator wizard
```

> **💡 Tip for AI-Assisted Migration:** If you're using a coding agent (like GitHub Copilot) to help with migration, ensure it has access to your Azure CLI session. This allows the agent to leverage Azure resources directly, making the migration process more efficient and accurate.

## Common Issues

### 403 Error: Azure Search Access Denied

This usually means RBAC roles are not configured correctly. Run:
```bash
oyd-migrator validate roles -g <your-resource-group>
```

See [RBAC Setup Guide](docs/RBAC.md) for configuration instructions.

### Discovery Takes Too Long

Use resource group filtering to speed up discovery:
```bash
oyd-migrator discover all -g <your-resource-group>
```

Or use the wizard's "Filter by resource group" option.

## Resources

- [Feature Comparison](FEATURE_COMPARISON.md)
- [Migration Guide](docs/MIGRATION_GUIDE.md)
- [RBAC Setup Guide](docs/RBAC.md)
- [Coding Agent Guide](AGENTS.md)
- [Foundry Agent Service Docs](https://learn.microsoft.com/azure/ai-foundry/agents)
- [Foundry IQ Knowledge Base](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/foundry-iq-connect)

## License

MIT
