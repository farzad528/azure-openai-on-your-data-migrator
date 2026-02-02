# RBAC Setup Guide

This guide explains how to configure Role-Based Access Control (RBAC) for Azure OpenAI On Your Data and Foundry Agent Service.

## Why RBAC Matters

When using **System Assigned Managed Identity** (recommended for production), Azure services need explicit permissions to communicate with each other. Without proper RBAC configuration, you'll encounter 403 (Forbidden) errors.

## Common Error

```
400: Invalid AzureCognitiveSearch configuration detected: Call to get Azure Search index failed.
Azure Search Error: 403, message='Server responded with status 403'
```

This error indicates missing RBAC role assignments between Azure OpenAI and Azure AI Search.

## Required Role Assignments

### For Azure OpenAI On Your Data

| Role | Assignee | Resource | Purpose |
|------|----------|----------|---------|
| **Search Index Data Reader** | Azure OpenAI Managed Identity | Azure AI Search | Query data from the index |
| **Search Service Contributor** | Azure OpenAI Managed Identity | Azure AI Search | Query index schema for field mapping |
| **Storage Blob Data Contributor** | Azure OpenAI Managed Identity | Storage Account | Read input, write preprocessed results |

### For Azure AI Search

| Role | Assignee | Resource | Purpose |
|------|----------|----------|---------|
| **Cognitive Services OpenAI Contributor** | Azure AI Search Managed Identity | Azure OpenAI | Access embedding endpoint |
| **Cognitive Services OpenAI Contributor** | Azure AI Search Managed Identity | Foundry Project | Access embedding endpoint |
| **Storage Blob Data Reader** | Azure AI Search Managed Identity | Storage Account | Read document and chunk blobs |

### For Foundry Agent Service

| Role | Assignee | Resource | Purpose |
|------|----------|----------|---------|
| **Reader** | Foundry Project | Azure Storage Private Endpoints | Read indexes in blob storage |
| **Cognitive Services OpenAI User** | Your identity / Web app | Azure OpenAI | Inference access |

## How to Configure RBAC

### Using Azure Portal

1. Navigate to the **target resource** (e.g., Azure AI Search)
2. Go to **Access control (IAM)** in the left menu
3. Click **+ Add** → **Add role assignment**
4. Select the role (e.g., "Search Index Data Reader")
5. Click **Next** → **Select members**
6. Search for the Azure OpenAI resource name (managed identity)
7. Click **Select** → **Review + assign**

### Using Azure CLI

```bash
# Get the managed identity principal ID
AOAI_PRINCIPAL_ID=$(az cognitiveservices account show \
  --name <aoai-resource-name> \
  --resource-group <resource-group> \
  --query identity.principalId -o tsv)

# Get the search service resource ID
SEARCH_RESOURCE_ID=$(az search service show \
  --name <search-service-name> \
  --resource-group <resource-group> \
  --query id -o tsv)

# Assign Search Index Data Reader role
az role assignment create \
  --assignee $AOAI_PRINCIPAL_ID \
  --role "Search Index Data Reader" \
  --scope $SEARCH_RESOURCE_ID

# Assign Search Service Contributor role
az role assignment create \
  --assignee $AOAI_PRINCIPAL_ID \
  --role "Search Service Contributor" \
  --scope $SEARCH_RESOURCE_ID
```

### Using the OYD Migrator

The migrator includes a validation command to check RBAC configuration:

```bash
oyd-migrator validate roles -g <resource-group>
```

This will check if the required role assignments are in place and report any missing permissions.

## Verifying Configuration

After configuring RBAC, you can verify the setup:

1. **Test the OYD connection**: Try a chat completion with your OYD-enabled deployment in Azure OpenAI Studio
2. **Run the migrator validation**: `oyd-migrator validate roles -g <resource-group>`
3. **Check Activity Logs**: Azure Portal → Resource → Activity log → Look for role assignment events

## Troubleshooting

### "403 Forbidden" after adding roles

Role assignments can take **up to 10 minutes** to propagate. Wait and retry.

### "Identity not found"

Ensure the Azure OpenAI resource has a System Assigned Managed Identity enabled:
1. Go to Azure Portal → Azure OpenAI resource
2. Click **Identity** in the left menu
3. Set **System assigned** to **On**
4. Click **Save**

### Still getting errors?

Check if the search service requires private endpoint access. If so, additional network configuration may be needed.

## References

- [Azure OpenAI OYD Authentication](https://aka.ms/aoaioydauthentication)
- [Azure RBAC Overview](https://learn.microsoft.com/azure/role-based-access-control/overview)
- [Azure AI Search Security](https://learn.microsoft.com/azure/search/search-security-overview)
