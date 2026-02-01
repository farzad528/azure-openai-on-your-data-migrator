# OYD Migrator

CLI tool for migrating Azure OpenAI "On Your Data" (OYD) to Azure AI Foundry Agent Service.

## Why Migrate?

Azure OpenAI OYD is being deprecated as GPT-x models retire (March/June 2025). This tool helps you migrate to Foundry Agent Service with two options:

- **Azure AI Search Tool** - Direct index connection for simple RAG
- **Foundry IQ Knowledge Base** - MCP-based for advanced reasoning

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

## Requirements

- Python 3.10+
- Azure CLI (`az login`)
- Azure subscription with OYD configured

## Authentication

```bash
az login
oyd-migrator wizard
```

## Resources

- [Feature Comparison](FEATURE_COMPARISON.md)
- [Migration Guide](docs/MIGRATION_GUIDE.md)
- [Coding Agent Guide](AGENTS.md)
- [Foundry Agent Service Docs](https://learn.microsoft.com/azure/ai-foundry/agents)
- [Foundry IQ Knowledge Base](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/foundry-iq-connect)

## License

MIT
