# Azure OpenAI OYD vs Foundry Agent Service Feature Comparison

This document provides a comprehensive comparison of Azure OpenAI "On Your Data" (OYD) and the two migration target architectures available in Azure AI Foundry Agent Service.

## Overview

Azure OpenAI "On Your Data" is being deprecated as the GPT-x series models retire in March and June 2025. Microsoft recommends migrating to Azure AI Foundry Agent Service, which offers two approaches for grounded RAG scenarios:

1. **Foundry Agent Service + Azure AI Search Tool** - Direct index connection
2. **Foundry Agent Service + Foundry IQ Knowledge Base** - MCP-based advanced retrieval

## Feature Comparison Matrix

| Feature | OYD (Deprecated) | Foundry + AI Search Tool | Foundry + IQ Knowledge Base |
|---------|------------------|--------------------------|----------------------------|
| **Data Source Support** |
| Azure AI Search | ✅ | ✅ | ✅ |
| Azure Blob Storage | ✅ | Via indexer | ✅ |
| Azure Cosmos DB | ✅ | ❌ | ❌ |
| SharePoint | ❌ | ❌ | ✅ |
| OneLake | ❌ | ❌ | ✅ |
| Web URLs | ✅ | ❌ | ✅ |
| **Search Capabilities** |
| Keyword Search | ✅ | ✅ | ✅ |
| Semantic Search | ✅ | ✅ | ✅ |
| Vector Search | ✅ | ✅ | ✅ |
| Hybrid Search | ✅ | ✅ | ✅ |
| Query Decomposition | ❌ | ❌ | ✅ |
| Multi-technique Retrieval | ❌ | ❌ | ✅ |
| **Multi-Source** |
| Multiple Indexes | ❌ | ✅ | ✅ |
| Mixed Source Types | ❌ | ✅ (via tools) | ✅ |
| **Agent Capabilities** |
| Multi-turn Conversations | ❌ (stateless) | ✅ (threads) | ✅ (threads) |
| Tool Orchestration | ❌ | ✅ | ✅ |
| Code Interpreter | ❌ | ✅ | ✅ |
| Function Calling | ❌ | ✅ | ✅ |
| File Handling | ❌ | ✅ | ✅ |
| Agentic Reasoning | ❌ | Basic | Full |
| **Retrieval Quality** |
| Semantic Reranking | ✅ (extra cost) | Via query_type | Built-in |
| Reranker Threshold | ❌ | ❌ | ✅ (0.0-4.0) |
| Top-K Configuration | ✅ (3-20) | ✅ (top_k param) | ✅ |
| Strictness Control | ✅ (1-5) | Via filter | Via reranker |
| **Response Features** |
| Citations | ✅ | ✅ (url_citation) | ✅ (references) |
| Activity Trace | ❌ | ❌ | ✅ |
| Token Usage Breakdown | Limited | ✅ | ✅ (detailed) |
| Streaming | ✅ | ✅ | ✅ |
| **Enterprise Features** |
| Managed Identity | ✅ | ✅ | ✅ |
| VNet Support | ✅ | ✅ (Standard) | ✅ (Standard) |
| Private Endpoints | ✅ | ✅ (Standard) | ✅ (Standard) |
| Document-level ACLs | ✅ (Entra groups) | Via filter param | Via ACL header |
| RBAC | ✅ | ✅ | ✅ |
| **Configuration** |
| System Message | role_information | instructions | instructions |
| In-Scope Filtering | ✅ | Via instructions | ✅ |
| OData Filters | ✅ | ✅ | ✅ (filterAddOn) |
| **Model Support** |
| GPT-4o | ✅ (retiring) | ✅ | ✅ |
| GPT-4.1 | ❌ | ✅ | ✅ |
| GPT-4.1-mini | ❌ | ✅ | ✅ |
| o1/o3 models | ❌ | ❌ | ❌ |
| **API & SDK** |
| REST API | ✅ | ✅ | ✅ |
| Python SDK | ✅ | ✅ | ✅ |
| .NET SDK | ✅ | ✅ | ✅ |
| JavaScript SDK | ✅ | ✅ | ✅ |
| **Status** |
| API Status | Deprecated | GA | Preview |
| Support | Limited | Full | Preview |

## Detailed Comparison

### Azure AI Search Tool Approach

**Best for:**
- Simple RAG scenarios with existing search indexes
- Direct migration from OYD with minimal changes
- Applications that need precise control over search parameters
- Single-index or few-index scenarios

**Advantages:**
- Simpler setup and configuration
- Direct control over query type and parameters
- Lower latency for straightforward queries
- GA status with full support

**Limitations:**
- No query decomposition
- Manual multi-index orchestration
- Less sophisticated retrieval strategies

**Configuration Example:**
```python
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

### Foundry IQ Knowledge Base Approach

**Best for:**
- Complex reasoning scenarios
- Multi-source retrieval (Search, SharePoint, OneLake, Web)
- Applications that benefit from query planning
- Scenarios requiring detailed activity tracing

**Advantages:**
- Automatic query decomposition
- Multi-technique retrieval strategies
- Built-in semantic reranking with threshold control
- Detailed activity traces for debugging
- Support for diverse knowledge sources

**Limitations:**
- Preview status (not recommended for production)
- Requires Knowledge Base setup in Azure AI Search
- Per-request ACL headers not supported in agents
- Higher complexity

**Configuration Example:**
```python
mcp_tool = MCPTool(
    server_label="knowledge_base",
    server_url=f"{search_endpoint}/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview",
    require_approval="never",
    allowed_tools=["knowledge_base_retrieve"],
    project_connection_id=connection_id,
)
```

## Migration Recommendations

### Choose Azure AI Search Tool when:
- ✅ You have a working OYD setup and want minimal changes
- ✅ Your queries are straightforward (single intent)
- ✅ You need GA-level support and stability
- ✅ You're using a single search index
- ✅ Latency is critical

### Choose Foundry IQ Knowledge Base when:
- ✅ You need advanced reasoning over multiple sources
- ✅ Your queries are complex (multi-intent, comparative)
- ✅ You want detailed retrieval activity traces
- ✅ You're using SharePoint, OneLake, or Web sources
- ✅ You can accept preview-level stability

## Enterprise Considerations

### VNet and Private Endpoints

Both approaches support VNet integration, but with requirements:

1. **Standard Deployment Required**: Basic deployments don't support private endpoints
2. **Same-Tenant Requirement**: Search service and Foundry project must be in the same tenant
3. **Network Configuration**: Ensure network paths are properly configured

### Document-Level Access Control

| Approach | Implementation |
|----------|----------------|
| OYD | Microsoft Entra group-based filtering |
| AI Search Tool | Use `filter` parameter with security trimming |
| Knowledge Base | Pass `x-ms-query-source-authorization` header (limited in agents) |

**Note**: For per-user ACLs with Knowledge Base, use Azure OpenAI Responses API directly instead of Foundry Agent Service.

## Token and Cost Considerations

### OYD Token Budget
- 20% reserved for response
- 80% for prompt, context, documents

### Foundry Agent Service
- More flexible token allocation
- Separate tracking for:
  - Query planning tokens
  - Retrieval tokens
  - Synthesis tokens
  - Agentic reasoning tokens

## Related Resources

- [Azure OpenAI On Your Data Documentation](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/use-your-data)
- [Foundry Agent Service - Azure AI Search Tool](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools/ai-search)
- [Foundry IQ Knowledge Base](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/foundry-iq-connect?view=foundry&tabs=foundry%2Cpython)
- [Model Retirements](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/model-retirements)

---

*This comparison was generated by oyd-foundry-migrator. For updates, run `oyd-migrator generate comparison`.*
