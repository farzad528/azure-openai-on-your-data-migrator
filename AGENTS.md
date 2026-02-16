# Coding Agent Guide

Instructs coding agents on how to work with the OYD Foundry Migrator codebase and assist users with migrations.

## Project Structure

```
oyd_migrator/
├── cli/
│   ├── commands/      # discover, migrate, validate, generate commands
│   └── wizards/       # Interactive wizard steps
├── core/              # Config, constants, exceptions
├── models/            # Data models (OYD, Foundry, Search, Migration)
├── services/          # Azure service integrations
└── generators/        # Code and report generators
```

## Key Files

- `oyd_migrator/cli/wizards/migration_wizard.py` — Main migration flow
- `oyd_migrator/services/agent_builder.py` — Creates Foundry agents
- `oyd_migrator/services/connection_manager.py` — Manages Azure connections
- `oyd_migrator/models/migration.py` — Migration state and configuration
- `FEATURE_COMPARISON.md` — Decision matrix for migration paths

## CLI Commands

```bash
pip install -e .
oyd-migrator wizard                              # Interactive migration
oyd-migrator discover all -g <resource-group>    # Discover OYD resources
oyd-migrator compare                             # Feature comparison matrix
oyd-migrator validate agent <name> --project-endpoint <url>
oyd-migrator generate python <name> --project-endpoint <url>
oyd-migrator migrate sessions                    # List saved sessions
oyd-migrator migrate interactive --resume <id>   # Resume session
```

## Migration Paths

| Scenario | Path |
|----------|------|
| Simple RAG, single index | Azure AI Search Tool |
| GA stability required | Azure AI Search Tool |
| Complex queries, multi-source | Foundry IQ Knowledge Base |
| SharePoint/OneLake sources | Foundry IQ Knowledge Base |

## Environment Variables

```bash
OYD_MIGRATOR_CONFIG_DIR=~/.oyd-migrator
OYD_MIGRATOR_LOG_LEVEL=DEBUG
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
```

## Azure SDK Skills (Reference)

For SDK-level guidance on the Azure services used by this tool, refer to the Microsoft-maintained Copilot Skills:

- [Azure AI Search — Python](https://github.com/microsoft/skills/tree/main/.github/skills/azure-search-documents-py)
- [Azure AI Search — TypeScript](https://github.com/microsoft/skills/tree/main/.github/skills/azure-search-documents-ts)
- [Azure AI Search — .NET](https://github.com/microsoft/skills/tree/main/.github/skills/azure-search-documents-dotnet)
- [Azure OpenAI — .NET](https://github.com/microsoft/skills/tree/main/.github/skills/azure-ai-openai-dotnet)
- [Azure AI Projects — Python](https://github.com/microsoft/skills/tree/main/.github/skills/azure-ai-projects-py)

## Agent Guidelines

1. Run discovery before migration to understand existing resources.
2. Use the wizard — it handles dependencies and validation automatically.
3. Check `FEATURE_COMPARISON.md` to guide migration path selection.
4. Generate SDK samples after migration for integration testing.
5. Resume interrupted sessions rather than restarting.
