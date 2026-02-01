# Coding Agent Guide

This document helps coding agents (GitHub Copilot, Claude Code, etc.) assist with OYD to Foundry migrations.

## Overview

This CLI tool migrates Azure OpenAI "On Your Data" configurations to Azure AI Foundry Agent Service. Agents can help users through the interactive wizard or automate migration steps.

## Using the CLI Wizard

The wizard is the primary migration path. Run it interactively:

```bash
# Install the tool first
pip install -e .

# Start the wizard
oyd-migrator wizard
```

### Wizard Steps

1. **Authentication** - Prompts for Azure login if needed
2. **Discovery** - Finds OYD configurations and search indexes in the subscription
3. **Path Selection** - Choose between AI Search Tool or Knowledge Base approach
4. **Configuration** - Maps OYD settings to Foundry equivalents
5. **Migration** - Creates connections, knowledge bases, and agents
6. **Validation** - Tests the migrated agent with sample queries

## Agent Assistance Patterns

### Helping Users Start

When a user wants to migrate their OYD setup:

```bash
# Ensure they're logged into Azure
az login

# Run discovery first to see what needs migrating
oyd-migrator discover all

# Then start the interactive wizard
oyd-migrator wizard
```

### Resuming a Session

The wizard saves progress. To resume:

```bash
# List saved sessions
oyd-migrator migrate sessions

# Resume specific session
oyd-migrator migrate interactive --resume <session-id>
```

### Generating Code Samples

After migration, generate SDK samples:

```bash
# Python SDK sample
oyd-migrator generate python <agent-name> --project-endpoint <endpoint>

# cURL commands
oyd-migrator generate curl <agent-name> --project-endpoint <endpoint>
```

## Migration Path Decision

Help users choose the right path:

| Scenario | Recommendation |
|----------|----------------|
| Simple RAG, single index | Azure AI Search Tool |
| Need GA stability | Azure AI Search Tool |
| Complex queries, multi-source | Foundry IQ Knowledge Base |
| SharePoint/OneLake sources | Foundry IQ Knowledge Base |

Run `oyd-migrator compare` to show the full feature matrix.

## Common Tasks

### Validate Existing Resources

```bash
# Check connection to search service
oyd-migrator validate connection <connection-name> --project-endpoint <endpoint>

# Test migrated agent
oyd-migrator validate agent <agent-name> --project-endpoint <endpoint>
```

### Debug Issues

```bash
# Verbose output for troubleshooting
oyd-migrator --verbose wizard

# Check logs
export OYD_MIGRATOR_LOG_LEVEL=DEBUG
oyd-migrator wizard
```

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

## Key Files for Agents

- `oyd_migrator/cli/wizards/migration_wizard.py` - Main migration flow
- `oyd_migrator/services/agent_builder.py` - Creates Foundry agents
- `oyd_migrator/services/connection_manager.py` - Manages Azure connections
- `oyd_migrator/models/migration.py` - Migration state and configuration
- `FEATURE_COMPARISON.md` - Decision matrix for migration paths

## Environment Variables

```bash
# Optional configuration
OYD_MIGRATOR_CONFIG_DIR=~/.oyd-migrator
OYD_MIGRATOR_LOG_LEVEL=DEBUG

# Azure auth (if not using az login)
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
```

## Tips for Coding Agents

1. **Always run discovery first** - Understand what resources exist before migrating
2. **Use the wizard** - It handles dependencies and validation automatically
3. **Check feature comparison** - Help users choose the right migration path
4. **Generate samples after migration** - Provide working code for integration
5. **Resume sessions** - Don't restart if a migration was interrupted
