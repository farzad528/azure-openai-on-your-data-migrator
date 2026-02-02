# OYD Migrator

CLI tool for migrating Azure OpenAI "On Your Data" (OYD) to Azure AI Foundry Agent Service.

## Why Migrate?

Azure OpenAI OYD is being deprecated as GPT-x models retire (March/June 2025). This tool helps you migrate to Foundry Agent Service with two options:

- **Azure AI Search Tool** - Direct index connection for simple RAG
- **Foundry IQ Knowledge Base** - MCP-based for advanced reasoning

## Prerequisites

Before starting the migration, ensure you have the following:

### 1. Azure Resources

You'll need existing Azure resources with "On Your Data" (OYD) configured:

- **Azure OpenAI resource** with OYD-enabled deployments
  - Resource name (e.g., `my-openai-resource`)
  - Resource group name
  - Deployment name(s) using OYD
- **Azure AI Search service** connected to your OYD deployments
  - Search service name
  - Search index name(s) referenced in OYD configurations
- **Azure subscription ID** where these resources are located

The migration wizard will **automatically discover** these resources during the discovery phase, so you don't need to manually collect all details beforehand. However, knowing your resource names will help verify the discovery results.

### 2. Required Permissions

Your Azure account needs the following RBAC roles:

**For reading OYD configurations:**
- `Cognitive Services OpenAI User` or `Cognitive Services OpenAI Contributor` on the Azure OpenAI resource

**For accessing search indexes:**
- `Search Index Data Reader` or `Search Index Data Contributor` on the Azure AI Search service
- `Search Service Contributor` for creating connections

**For creating Foundry resources:**
- `Azure AI User` or `Azure AI Project Manager` on the target Azure AI Foundry project (or resource group to create new projects)

### 3. Software Requirements

- **Python 3.10 or higher**
- **Azure CLI** installed and configured (`az --version` to verify)
  - Install from: https://learn.microsoft.com/cli/azure/install-azure-cli
- **Azure authentication** via one of:
  - Azure CLI (`az login`) - Recommended for interactive use
  - Service Principal (client ID + secret)
  - Managed Identity (for Azure-hosted environments)

### 4. Before Running the Wizard

1. **Authenticate with Azure:**
   ```bash
   az login
   ```

2. **Verify access to your subscription:**
   ```bash
   az account show
   az account set --subscription <your-subscription-id>
   ```

3. **Optional: Verify your OYD resources** (the wizard will do this automatically):
   ```bash
   # List AOAI deployments
   az cognitiveservices account deployment list \
     --name <openai-resource-name> \
     --resource-group <resource-group>
   
   # List search indexes
   az search index list \
     --service-name <search-service-name> \
     --resource-group <resource-group>
   ```

## Quick Start

```bash
# Install
pip install -e .

# Run interactive wizard
oyd-migrator wizard
```

## Commands

```bash
oyd-migrator discover all        # Find OYD configurations and indexes
oyd-migrator compare             # View feature comparison matrix
oyd-migrator migrate interactive # Start migration wizard
oyd-migrator validate agent <name> --project-endpoint <url>
oyd-migrator generate python <name> --project-endpoint <url>
```

## Resources

- [Feature Comparison](FEATURE_COMPARISON.md)
- [Migration Guide](docs/MIGRATION_GUIDE.md)
- [Coding Agent Guide](AGENTS.md)
- [Foundry Agent Service Docs](https://learn.microsoft.com/azure/ai-foundry/agents)
- [Foundry IQ Knowledge Base](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/foundry-iq-connect)

## License

MIT
