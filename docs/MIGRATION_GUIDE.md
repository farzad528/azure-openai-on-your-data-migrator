# Migrating from Azure OpenAI "On Your Data" to Foundry Agent Service: A Complete Guide

**TL;DR:** Azure OpenAI "On Your Data" (OYD) is being deprecated as GPT-4o and earlier models retire in 2025. This guide walks you through migrating to Azure AI Foundry Agent Service, with two paths: the Azure AI Search Tool for simple RAG scenarios, or Foundry IQ Knowledge Base for advanced reasoning.

---

## Table of Contents

1. [Why Migrate? Understanding the Deprecation](#why-migrate-understanding-the-deprecation)
2. [Architecture Comparison: OYD vs Foundry Agents](#architecture-comparison-oyd-vs-foundry-agents)
3. [Choosing Your Migration Path](#choosing-your-migration-path)
4. [Path A: Foundry Agent + Azure AI Search Tool](#path-a-foundry-agent--azure-ai-search-tool)
5. [Path B: Foundry Agent + Foundry IQ Knowledge Base](#path-b-foundry-agent--foundry-iq-knowledge-base)
6. [Step-by-Step Migration Process](#step-by-step-migration-process)
7. [Handling Enterprise Scenarios](#handling-enterprise-scenarios)
8. [Testing Your Migration](#testing-your-migration)
9. [Code Samples](#code-samples)
10. [Troubleshooting](#troubleshooting)

---

## Why Migrate? Understanding the Deprecation

Azure OpenAI "On Your Data" (OYD) was introduced as a quick way to ground GPT models with your enterprise data. You could point it at an Azure AI Search index, and it would automatically retrieve relevant documents to answer questions.

**However, OYD has significant limitations:**

- **Stateless**: No conversation memory between turns
- **Single-index**: Can only query one search index at a time
- **Limited reasoning**: Simple retrieve-and-generate pattern
- **No tool orchestration**: Can't combine search with other capabilities
- **Model dependency**: Tied to GPT-4o and earlier models being retired

**The retirement timeline:**

| Model | Retirement Date |
|-------|-----------------|
| GPT-4o (2024-05-13) | March 2025 |
| GPT-4o (2024-08-06) | June 2025 |
| GPT-4 Turbo | June 2025 |

If your application uses OYD with these models, you need to migrate before these dates.

---

## Architecture Comparison: OYD vs Foundry Agents

### How OYD Works

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Client    │────▶│  Azure OpenAI    │────▶│  Azure Search   │
│             │◀────│  (OYD enabled)   │◀────│     Index       │
└─────────────┘     └──────────────────┘     └─────────────────┘
                           │
                    Retrieval + Generation
                    in single API call
```

OYD bundles retrieval and generation into a single, opaque operation. You configure data sources in the deployment, and the model handles everything internally.

### How Foundry Agents Work

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Client    │────▶│  Foundry Agent   │────▶│     Tools       │
│             │◀────│   (Threads)      │◀────│  - AI Search    │
└─────────────┘     └──────────────────┘     │  - Code Interp  │
                           │                 │  - Functions    │
                    Agentic reasoning        │  - Knowledge KB │
                    with tool calls          └─────────────────┘
```

Foundry Agents use an agentic architecture:

1. **Threads**: Persistent conversation state
2. **Tools**: Modular capabilities the agent can invoke
3. **Reasoning**: The agent decides when and how to use tools
4. **Orchestration**: Multiple tools can be combined in a single response

---

## Choosing Your Migration Path

### Feature Comparison Matrix

| Feature | OYD (Deprecated) | Foundry + Search Tool | Foundry + IQ KB |
|---------|------------------|----------------------|-----------------|
| **Azure AI Search** | ✅ | ✅ | ✅ |
| **Semantic/Vector/Hybrid Search** | ✅ | ✅ | ✅ |
| **Multi-Index Support** | ❌ | ✅ | ✅ |
| **Multi-Source Types** | Limited | ✅ (via tools) | ✅ |
| **Citations** | ✅ | ✅ (url_citation) | ✅ (references) |
| **Managed Identity** | ✅ | ✅ | ✅ |
| **VNet/Private Endpoints** | ✅ | ✅ (Standard) | ✅ (Standard) |
| **Document ACLs** | Entra groups | filter param | ACL header |
| **Multi-turn Conversations** | ❌ | ✅ | ✅ |
| **Tool Orchestration** | ❌ | ✅ | ✅ |
| **Code Interpreter** | ❌ | ✅ | ✅ |
| **Query Decomposition** | ❌ | ❌ | ✅ |
| **Agentic Reasoning** | ❌ | Basic | Full |
| **API Status** | Deprecated | GA | Preview |

### Decision Guide

**Choose Path A (Azure AI Search Tool) if:**
- You have existing search indexes that work well
- You want a straightforward 1:1 migration
- You need GA (Generally Available) stability
- Your queries are relatively simple
- You want precise control over search parameters

**Choose Path B (Foundry IQ Knowledge Base) if:**
- You need advanced reasoning over your data
- You want query decomposition (breaking complex questions into sub-queries)
- You need multi-source retrieval (Search, SharePoint, OneLake, Web)
- You want detailed activity tracing
- You're okay with Preview status

---

## Path A: Foundry Agent + Azure AI Search Tool

The Azure AI Search Tool (`AzureAISearchAgentTool`) provides direct integration between Foundry Agents and your existing search indexes.

### How It Works

1. **Project Connection**: You create a connection in your Foundry project that points to your Azure AI Search service
2. **Tool Configuration**: The agent is configured with the search tool, specifying which indexes to query
3. **Runtime Behavior**: When the agent needs information, it invokes the search tool and receives results with citations

### Key Concepts

#### Project Connections

Before the agent can query your search index, you need a **project connection**. This is a secure reference to your Azure AI Search service:

```python
from azure.ai.ml import MLClient
from azure.ai.ml.entities import AzureAISearchConnection

# Create connection to your search service
connection = AzureAISearchConnection(
    name="my-search-connection",
    endpoint="https://my-search.search.windows.net",
    api_key="<your-api-key>",  # Or use managed identity
)

ml_client.connections.create_or_update(connection)
```

#### Tool Configuration

The search tool is configured with:

- **Index name**: Which index to query
- **Query type**: Keyword, semantic, vector, or hybrid
- **Top K**: Number of results to return
- **Filter**: Optional OData filter expression

```python
from azure.ai.projects.models import (
    AzureAISearchAgentTool,
    AzureAISearchToolResource,
    AISearchIndexResource,
    AzureAISearchQueryType,
)

search_tool = AzureAISearchAgentTool(
    azure_ai_search=AzureAISearchToolResource(
        indexes=[
            AISearchIndexResource(
                project_connection_id=connection_id,
                index_name="products-index",
                query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
                top_k=5,
            ),
        ]
    )
)
```

#### Citation Handling

When the agent retrieves information, it includes citations in the response. These appear as `url_citation` annotations:

```json
{
  "type": "url_citation",
  "url": "https://my-search.search.windows.net/indexes/products/docs/doc-123",
  "title": "Product Manual",
  "start_index": 45,
  "end_index": 120
}
```

### Migration Mapping

Here's how OYD configuration maps to the Search Tool:

| OYD Parameter | Search Tool Equivalent |
|---------------|----------------------|
| `data_sources[].endpoint` | Project connection endpoint |
| `data_sources[].index_name` | `AISearchIndexResource.index_name` |
| `data_sources[].query_type` | `AzureAISearchQueryType` enum |
| `data_sources[].semantic_configuration` | Configured in index |
| `data_sources[].top_n_documents` | `top_k` parameter |
| `data_sources[].filter` | `filter` parameter |
| `data_sources[].role_information` | Agent `instructions` |
| `data_sources[].in_scope` | Handled via instructions |

---

## Path B: Foundry Agent + Foundry IQ Knowledge Base

Foundry IQ Knowledge Base uses the **Model Context Protocol (MCP)** to provide a more sophisticated retrieval experience.

### How It Works

1. **Knowledge Base Creation**: You create a knowledge base that connects to your data sources
2. **MCP Tool**: The agent uses an MCP tool to communicate with the knowledge base
3. **Query Planning**: The knowledge base can decompose complex queries into sub-queries
4. **Semantic Reranking**: Results are reranked for relevance before being returned

### Key Concepts

#### Knowledge Bases

A Foundry IQ Knowledge Base is a managed resource that:

- Connects to one or more data sources (Azure AI Search, SharePoint, OneLake, Web URLs)
- Handles query decomposition automatically
- Provides semantic reranking
- Supports document-level ACLs via headers

#### MCP (Model Context Protocol)

MCP is a standardized protocol for tools to communicate with agents. The knowledge base exposes an MCP endpoint that the agent calls:

```
POST {search_endpoint}/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview
```

The agent uses the `knowledge_base_retrieve` tool to query the knowledge base.

#### Tool Configuration

```python
from azure.ai.projects.models import MCPTool

mcp_kb_tool = MCPTool(
    server_label="knowledge-base",
    server_url=f"{search_endpoint}/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview",
    require_approval="never",
    allowed_tools=["knowledge_base_retrieve"],
    project_connection_id=mcp_connection_name,
)
```

#### Citation Handling

Foundry IQ returns citations in a `references` format that includes more metadata:

```json
{
  "references": [
    {
      "id": "doc-123",
      "title": "Product Manual",
      "url": "https://...",
      "chunk_id": "chunk-456",
      "relevance_score": 0.95
    }
  ]
}
```

### Query Decomposition Example

When you ask: *"Compare the pricing and features of Product A vs Product B"*

**Without query decomposition (OYD/Search Tool):**
- Single query: "Compare pricing features Product A Product B"
- May miss relevant documents about each product

**With query decomposition (Foundry IQ):**
1. Sub-query 1: "Product A pricing"
2. Sub-query 2: "Product A features"
3. Sub-query 3: "Product B pricing"
4. Sub-query 4: "Product B features"
5. Results combined and reranked

This approach retrieves more comprehensive information for complex questions.

---

## Step-by-Step Migration Process

### Prerequisites

Before starting migration:

1. **Azure CLI authenticated**: `az login`
2. **Appropriate RBAC roles**:
   - `Cognitive Services Contributor` on AOAI resources
   - `Search Service Contributor` on AI Search
   - `Contributor` on Foundry project resource group
3. **Existing resources identified**:
   - AOAI deployments with OYD configured
   - AI Search indexes being used

### Stage 1: Discovery

First, inventory your existing OYD configurations:

```bash
# Using the CLI tool
oyd-migrator discover aoai --subscription <sub-id>

# Or manually via Azure CLI
az cognitiveservices account deployment list \
  --name <aoai-resource> \
  --resource-group <rg>
```

For each deployment, extract:
- Deployment name and model
- Data source configurations
- Query types and parameters
- System messages (role_information)

### Stage 2: Foundry Project Setup

Create or connect to a Foundry project:

```bash
# Create new project
az ai project create \
  --name "migrated-assistant-project" \
  --resource-group <rg> \
  --location eastus

# Or use existing
az ai project show --name <existing-project>
```

### Stage 3: Create Project Connections

For each AI Search service used by OYD:

```python
from azure.ai.ml import MLClient
from azure.ai.ml.entities import AzureAISearchConnection
from azure.identity import DefaultAzureCredential

ml_client = MLClient(
    credential=DefaultAzureCredential(),
    subscription_id="<sub-id>",
    resource_group_name="<rg>",
    workspace_name="<project-name>",
)

# Create connection (API key auth)
connection = AzureAISearchConnection(
    name="search-connection",
    endpoint="https://my-search.search.windows.net",
    api_key="<api-key>",
)
ml_client.connections.create_or_update(connection)

# Or with managed identity (recommended)
connection = AzureAISearchConnection(
    name="search-connection",
    endpoint="https://my-search.search.windows.net",
    # No api_key = uses managed identity
)
```

### Stage 4: Create the Agent

#### Path A: Search Tool Agent

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    AzureAISearchAgentTool,
    AzureAISearchToolResource,
    AISearchIndexResource,
    AzureAISearchQueryType,
)
from azure.identity import DefaultAzureCredential

# Connect to project
project_client = AIProjectClient(
    credential=DefaultAzureCredential(),
    endpoint="https://<resource>.services.ai.azure.com/api/projects/<project>",
)

# Get connection ID
connections = project_client.connections.list()
connection_id = next(c.id for c in connections if c.name == "search-connection")

# Configure search tool
search_tool = AzureAISearchAgentTool(
    azure_ai_search=AzureAISearchToolResource(
        indexes=[
            AISearchIndexResource(
                project_connection_id=connection_id,
                index_name="products-index",
                query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
                top_k=5,
            ),
        ]
    )
)

# Create agent with migrated instructions
instructions = """You are a helpful product assistant.

When answering questions:
1. Always search the knowledge base for relevant information
2. Cite your sources using the provided citations
3. If you cannot find relevant information, say so clearly
4. Stay focused on product-related topics

This assistant was migrated from Azure OpenAI On Your Data."""

agent = project_client.agents.create_version(
    agent_name="migrated-product-assistant",
    definition=PromptAgentDefinition(
        model="gpt-4.1",
        instructions=instructions,
        tools=[search_tool],
    ),
)

print(f"Created agent: {agent.name} (version {agent.version})")
```

#### Path B: Knowledge Base Agent

```python
from azure.ai.projects.models import MCPTool

# First, create the knowledge base (via Azure portal or REST API)
kb_name = "products-kb"
search_endpoint = "https://my-search.search.windows.net"

# Create MCP connection for the knowledge base
mcp_connection = MCPServerConnection(
    name="kb-mcp-connection",
    endpoint=f"{search_endpoint}/knowledgebases/{kb_name}/mcp",
    api_version="2025-11-01-preview",
)
ml_client.connections.create_or_update(mcp_connection)

# Configure MCP tool
mcp_kb_tool = MCPTool(
    server_label="knowledge-base",
    server_url=f"{search_endpoint}/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview",
    require_approval="never",
    allowed_tools=["knowledge_base_retrieve"],
    project_connection_id="kb-mcp-connection",
)

# Create agent
agent = project_client.agents.create_version(
    agent_name="migrated-kb-assistant",
    definition=PromptAgentDefinition(
        model="gpt-4.1-mini",
        instructions=instructions,
        tools=[mcp_kb_tool],
    ),
)
```

### Stage 5: Test the Migration

Run test queries to validate the migration:

```python
# Create a thread
thread = project_client.agents.threads.create()

# Send a test message
message = project_client.agents.messages.create(
    thread_id=thread.id,
    role="user",
    content="What products do you have for home automation?",
)

# Run the agent
run = project_client.agents.runs.create_and_process(
    thread_id=thread.id,
    agent_id=agent.id,
)

# Check the response
messages = project_client.agents.messages.list(thread_id=thread.id)
assistant_message = next(m for m in messages if m.role == "assistant")

print(f"Response: {assistant_message.content[0].text.value}")

# Check for citations
for annotation in assistant_message.content[0].text.annotations:
    if annotation.type == "url_citation":
        print(f"Citation: {annotation.url_citation.title}")
```

---

## Handling Enterprise Scenarios

### VNet and Private Endpoints

Both Foundry Agent paths support VNet integration, but require **Standard deployment**:

1. **Deploy agent with Standard tier**:
   ```bash
   az ai project agent-deployment create \
     --name "secure-agent" \
     --project <project> \
     --sku Standard
   ```

2. **Configure private endpoints** for:
   - Foundry project endpoint
   - Azure AI Search service
   - Any other connected resources

3. **Ensure network connectivity** between all resources

### Document-Level ACLs

If your OYD configuration uses Entra ID groups for document security:

#### Path A: Search Tool
Use the `filter` parameter with security trimming:

```python
AISearchIndexResource(
    ...
    filter="allowed_groups/any(g: g eq 'group-id')",
)
```

#### Path B: Knowledge Base
Use the `x-ms-query-source-authorization` header:

```python
# When creating the run, pass the user's token
run = project_client.agents.runs.create_and_process(
    thread_id=thread.id,
    agent_id=agent.id,
    additional_headers={
        "x-ms-query-source-authorization": f"Bearer {user_access_token}"
    },
)
```

### Managed Identity Authentication

For production workloads, use managed identity instead of API keys:

1. **Enable system-assigned identity** on your Foundry project
2. **Grant RBAC roles**:
   - `Search Index Data Reader` on AI Search
   - `Cognitive Services User` on any AOAI resources
3. **Create connections without API keys** (SDK uses managed identity automatically)

---

## Testing Your Migration

### Validation Checklist

| Test | What to Check |
|------|---------------|
| **Basic retrieval** | Agent finds relevant documents |
| **Citations** | Responses include source citations |
| **Query types** | Semantic/vector/hybrid works as expected |
| **Filters** | Security filters are applied correctly |
| **Multi-turn** | Conversation context is maintained |
| **Error handling** | Graceful handling when no results found |
| **Performance** | Response times are acceptable |

### Comparing OYD vs Migrated Responses

Run the same queries against both systems and compare:

```python
# Test query
test_queries = [
    "What is your return policy?",
    "Compare Product A and Product B",
    "How do I set up the device?",
]

for query in test_queries:
    oyd_response = call_oyd(query)
    agent_response = call_agent(query)

    print(f"Query: {query}")
    print(f"OYD: {oyd_response[:200]}...")
    print(f"Agent: {agent_response[:200]}...")
    print(f"Both have citations: {has_citations(oyd_response)} / {has_citations(agent_response)}")
    print("---")
```

---

## Code Samples

### Complete Python Example: Search Tool Agent

```python
"""
Complete example: Migrating OYD to Foundry Agent with Azure AI Search Tool
"""

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    AzureAISearchAgentTool,
    AzureAISearchToolResource,
    AISearchIndexResource,
    AzureAISearchQueryType,
)
from azure.identity import DefaultAzureCredential

# Configuration
PROJECT_ENDPOINT = "https://<resource>.services.ai.azure.com/api/projects/<project>"
CONNECTION_NAME = "search-connection"
INDEX_NAME = "products-index"
MODEL = "gpt-4.1"

def create_migrated_agent():
    """Create an agent that replicates OYD functionality."""

    # Initialize client
    client = AIProjectClient(
        credential=DefaultAzureCredential(),
        endpoint=PROJECT_ENDPOINT,
    )

    # Get connection ID
    connections = list(client.connections.list())
    connection = next(c for c in connections if c.name == CONNECTION_NAME)

    # Configure search tool (migrated from OYD settings)
    search_tool = AzureAISearchAgentTool(
        azure_ai_search=AzureAISearchToolResource(
            indexes=[
                AISearchIndexResource(
                    project_connection_id=connection.id,
                    index_name=INDEX_NAME,
                    query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
                    top_k=5,
                ),
            ]
        )
    )

    # Instructions (migrated from OYD role_information)
    instructions = """You are a helpful product assistant.

Always search the knowledge base before answering questions.
Cite your sources. If you cannot find relevant information, say so."""

    # Create agent
    agent = client.agents.create_version(
        agent_name="migrated-assistant",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=instructions,
            tools=[search_tool],
        ),
    )

    return client, agent


def chat(client, agent, user_message: str) -> str:
    """Send a message and get a response."""

    # Create thread
    thread = client.agents.threads.create()

    # Add user message
    client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message,
    )

    # Run agent
    run = client.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id,
    )

    # Get response
    messages = list(client.agents.messages.list(thread_id=thread.id))
    assistant_msg = next(m for m in messages if m.role == "assistant")

    response_text = assistant_msg.content[0].text.value

    # Extract citations
    citations = []
    for annotation in assistant_msg.content[0].text.annotations:
        if annotation.type == "url_citation":
            citations.append({
                "title": annotation.url_citation.title,
                "url": annotation.url_citation.url,
            })

    return response_text, citations


if __name__ == "__main__":
    client, agent = create_migrated_agent()
    print(f"Created agent: {agent.name}")

    response, citations = chat(client, agent, "What products do you offer?")
    print(f"\nResponse: {response}")
    print(f"\nCitations: {citations}")
```

### cURL Example

```bash
# Get access token
TOKEN=$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)

# Create a thread
THREAD_ID=$(curl -s -X POST \
  "https://<resource>.services.ai.azure.com/api/projects/<project>/agents/threads?api-version=2024-12-01-preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq -r '.id')

# Add a message
curl -X POST \
  "https://<resource>.services.ai.azure.com/api/projects/<project>/agents/threads/$THREAD_ID/messages?api-version=2024-12-01-preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "user", "content": "What products do you have?"}'

# Run the agent
RUN_ID=$(curl -s -X POST \
  "https://<resource>.services.ai.azure.com/api/projects/<project>/agents/threads/$THREAD_ID/runs?api-version=2024-12-01-preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "<agent-id>"}' | jq -r '.id')

# Poll for completion
while true; do
  STATUS=$(curl -s \
    "https://<resource>.services.ai.azure.com/api/projects/<project>/agents/threads/$THREAD_ID/runs/$RUN_ID?api-version=2024-12-01-preview" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')

  if [ "$STATUS" = "completed" ]; then break; fi
  sleep 1
done

# Get messages
curl -s \
  "https://<resource>.services.ai.azure.com/api/projects/<project>/agents/threads/$THREAD_ID/messages?api-version=2024-12-01-preview" \
  -H "Authorization: Bearer $TOKEN" | jq '.data[] | select(.role == "assistant") | .content[0].text'
```

---

## Troubleshooting

### Common Issues

#### "Connection not found"

**Symptom**: Agent creation fails with "connection not found"

**Solution**: Ensure the connection exists and the name matches exactly:
```python
connections = list(client.connections.list())
print([c.name for c in connections])  # List all connection names
```

#### "No results from search"

**Symptom**: Agent says it cannot find information, but the index has data

**Solutions**:
1. Verify the index name is correct
2. Check query type compatibility (e.g., vector search requires embeddings)
3. Test the search directly via Azure portal
4. Ensure the connection has proper permissions

#### "Citations missing"

**Symptom**: Responses don't include citations

**Solutions**:
1. Add explicit citation instructions: "Always cite your sources"
2. Verify the search tool is returning results (check run steps)
3. Ensure the index has appropriate metadata fields

#### "Authentication failed"

**Symptom**: 401 or 403 errors

**Solutions**:
1. For DefaultAzureCredential: Run `az login`
2. For managed identity: Ensure RBAC roles are assigned
3. For service principal: Verify client ID/secret are correct

### Getting Help

- [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-foundry/)
- [Azure AI Search Documentation](https://learn.microsoft.com/azure/search/)
- [GitHub Issues](https://github.com/Azure-Samples/azure-ai-search-knowledge-retrieval-demo/issues)

---

## Conclusion

Migrating from Azure OpenAI "On Your Data" to Foundry Agent Service is a significant upgrade:

- **From stateless to stateful**: Persistent conversation threads
- **From single-tool to multi-tool**: Combine search with code interpreter, functions, and more
- **From simple RAG to agentic RAG**: Let the model decide when and how to search
- **From deprecated to supported**: GPT-4.1 and future models

The migration CLI tool (`oyd-migrator`) automates much of this process:

```bash
pip install oyd-foundry-migrator
oyd-migrator wizard
```

Choose the path that fits your needs:
- **Search Tool** for simple, GA-stable migrations
- **Knowledge Base** for advanced reasoning and multi-source scenarios

Start your migration today to ensure continuity before the GPT-4o retirement dates.

---

*Last updated: January 2025*
