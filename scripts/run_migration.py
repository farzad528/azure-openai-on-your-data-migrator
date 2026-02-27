"""
Programmatic OYD-to-Foundry Migration Script
=============================================
Bypasses the interactive wizard UI and calls the Foundry Agent Service
REST APIs directly. Use this from CI/CD or coding agents that cannot
drive the interactive questionary prompts.

Usage:
    cd azure-openai-on-your-data-migrator
    python scripts/run_migration.py

Prerequisites:
    - az login (Azure CLI authenticated)
    - pip install -e .
    - Foundry project with model deployed
    - Search connection created in the Foundry project (via portal)

Environment variables (set before running):
    FOUNDRY_PROJECT_ENDPOINT  - e.g. https://<resource>.services.ai.azure.com/api/projects/<project>
    FOUNDRY_MODEL             - model deployment name, e.g. gpt-4o-mini
    SEARCH_CONNECTION_NAME    - connection name as shown in Foundry portal
    SEARCH_INDEX_NAME         - Azure AI Search index name
    SEARCH_QUERY_TYPE         - simple | semantic | vector | vector_semantic_hybrid
    AZURE_SEARCH_KEY          - (optional) search API key for OYD comparison queries
"""

import os
import sys
import time

import requests
from azure.identity import AzureCliCredential
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ============================================================
# CONFIGURATION — override via environment variables
# ============================================================

PROJECT_ENDPOINT = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://your-foundry-resource.services.ai.azure.com/api/projects/your-project-name",
)
MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4o-mini")
SEARCH_CONNECTION_NAME = os.environ.get("SEARCH_CONNECTION_NAME", "your-search-connection")
SEARCH_INDEX_NAME = os.environ.get("SEARCH_INDEX_NAME", "your-index-name")
SEARCH_QUERY_TYPE = os.environ.get("SEARCH_QUERY_TYPE", "semantic")
AGENT_NAME = os.environ.get("AGENT_NAME", "oyd-migrated-agent")
AGENT_INSTRUCTIONS = os.environ.get(
    "AGENT_INSTRUCTIONS",
    "You are a helpful assistant. Use the search tool to find information before answering.",
)

# OYD source for comparison (optional — leave blank to skip)
OYD_ENDPOINT = os.environ.get("OYD_ENDPOINT", "")
OYD_DEPLOYMENT = os.environ.get("OYD_DEPLOYMENT", "gpt-4o-mini")
OYD_SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY", "")  # never hardcode secrets

TEST_QUERIES = [
    "What information is available?",
    "Give me a summary of the main topics.",
]

API_VERSION = "2025-05-01"

# ============================================================


def get_token(credential, scope):
    return credential.get_token(scope).token


def get_connection_id(token):
    url = f"{PROJECT_ENDPOINT}/connections?api-version={API_VERSION}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    for conn in r.json().get("value", []):
        if conn["name"] == SEARCH_CONNECTION_NAME:
            return conn["id"]
    raise ValueError(
        f"Connection '{SEARCH_CONNECTION_NAME}' not found. "
        "Create it in the Foundry portal: Management > Connected resources > + New connection"
    )


def create_agent(token, connection_id):
    url = f"{PROJECT_ENDPOINT}/assistants?api-version={API_VERSION}"
    body = {
        "name": AGENT_NAME,
        "model": MODEL,
        "instructions": AGENT_INSTRUCTIONS,
        "tools": [{"type": "azure_ai_search"}],
        "tool_resources": {
            "azure_ai_search": {
                "indexes": [{
                    "index_connection_id": connection_id,
                    "index_name": SEARCH_INDEX_NAME,
                    "query_type": SEARCH_QUERY_TYPE,
                    "top_k": 5,
                }]
            }
        },
    }
    r = requests.post(url, json=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    r.raise_for_status()
    return r.json()


def query_agent(token, agent_id, query):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = PROJECT_ENDPOINT

    thread_id = requests.post(
        f"{base}/threads?api-version={API_VERSION}", json={}, headers=headers
    ).json()["id"]

    requests.post(
        f"{base}/threads/{thread_id}/messages?api-version={API_VERSION}",
        json={"role": "user", "content": query}, headers=headers,
    ).raise_for_status()

    run_id = requests.post(
        f"{base}/threads/{thread_id}/runs?api-version={API_VERSION}",
        json={"assistant_id": agent_id}, headers=headers,
    ).json()["id"]

    for _ in range(30):
        status = requests.get(
            f"{base}/threads/{thread_id}/runs/{run_id}?api-version={API_VERSION}",
            headers=headers,
        ).json().get("status", "")
        if status == "completed":
            break
        if status in ("failed", "cancelled", "expired"):
            return {"error": f"Run {status}"}
        time.sleep(2)

    for msg in requests.get(
        f"{base}/threads/{thread_id}/messages?api-version={API_VERSION}", headers=headers
    ).json().get("data", []):
        if msg["role"] == "assistant":
            for c in msg.get("content", []):
                if c.get("type") == "text":
                    return {
                        "response": c["text"]["value"],
                        "citations": len(c["text"].get("annotations", [])),
                    }
    return {"error": "No response"}


def query_oyd(query):
    if not OYD_ENDPOINT or not OYD_SEARCH_KEY:
        return None
    cred = AzureCliCredential(process_timeout=30)
    token = get_token(cred, "https://cognitiveservices.azure.com/.default")
    url = f"{OYD_ENDPOINT}/openai/deployments/{OYD_DEPLOYMENT}/chat/completions?api-version=2024-10-21"
    body = {
        "messages": [{"role": "user", "content": query}],
        "data_sources": [{
            "type": "azure_search",
            "parameters": {
                "endpoint": f"https://{SEARCH_CONNECTION_NAME}.search.windows.net",
                "index_name": SEARCH_INDEX_NAME,
                "authentication": {"type": "api_key", "key": OYD_SEARCH_KEY},
                "query_type": SEARCH_QUERY_TYPE,
            },
        }],
    }
    r = requests.post(url, json=body, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"
    })
    if r.ok:
        msg = r.json()["choices"][0]["message"]
        return {
            "response": msg["content"],
            "citations": len(msg.get("context", {}).get("citations", [])),
        }
    return {"error": r.text[:200]}


def main():
    console.print(Panel.fit(
        "[bold]OYD-to-Foundry Programmatic Migration[/bold]\n\n"
        "Migrates OYD configurations to Foundry Agent Service\n"
        "using direct REST API calls (no interactive prompts required).",
        title="Migration Script", border_style="cyan",
    ))

    # Validate required config
    if "your-foundry-resource" in PROJECT_ENDPOINT:
        console.print(
            "[red]✗ PROJECT_ENDPOINT is not configured.[/red]\n"
            "  Set the FOUNDRY_PROJECT_ENDPOINT environment variable or edit the script."
        )
        sys.exit(1)

    # Authenticate
    console.print("\n[dim]◐[/dim] Authenticating with Azure CLI...")
    credential = AzureCliCredential(process_timeout=30)
    token = get_token(credential, "https://ai.azure.com/.default")
    console.print("✓ Authentication successful.\n")

    # Look up connection
    console.print("[dim]◐[/dim] Looking up search connection...")
    connection_id = get_connection_id(token)
    console.print(f"✓ Connection found: {SEARCH_CONNECTION_NAME}\n")

    # Create agent
    console.print("[dim]◐[/dim] Creating Foundry agent...")
    agent = create_agent(token, connection_id)
    agent_id = agent["id"]
    console.print(f"✓ Agent created: {agent['name']}  (ID: {agent_id})\n")

    # Test
    console.print("[dim]◐[/dim] Testing migrated agent...\n")
    table = Table(title="Validation Results")
    table.add_column("Query", style="cyan", max_width=35)
    table.add_column("Foundry Response", style="green", max_width=55)
    table.add_column("Cites", justify="center")
    if OYD_ENDPOINT and OYD_SEARCH_KEY:
        table.add_column("OYD Response", style="yellow", max_width=55)
        table.add_column("Cites", justify="center")
        table.add_column("Match", justify="center")

    all_pass = True
    for query in TEST_QUERIES:
        fr = query_agent(token, agent_id, query)
        ft = fr.get("response", fr.get("error", ""))[:120]
        fc = str(fr.get("citations", 0))

        if OYD_ENDPOINT and OYD_SEARCH_KEY:
            oyd = query_oyd(query) or {}
            ot = oyd.get("response", oyd.get("error", "n/a"))[:120]
            oc = str(oyd.get("citations", 0))
            match = "✓" if "response" in fr else "✗"
            if match == "✗":
                all_pass = False
            table.add_row(query, ft, fc, ot, oc, match)
        else:
            ok = "✓" if "response" in fr else "✗"
            if ok == "✗":
                all_pass = False
            table.add_row(query, ft, fc)

    console.print(table)
    console.print()

    border = "green" if all_pass else "red"
    console.print(Panel.fit(
        f"{'✓' if all_pass else '✗'} Migration {'complete' if all_pass else 'completed with issues'}!\n\n"
        f"Agent:   {AGENT_NAME} ({agent_id})\n"
        f"Project: {PROJECT_ENDPOINT}\n"
        f"Model:   {MODEL}\n"
        f"Index:   {SEARCH_INDEX_NAME} ({SEARCH_QUERY_TYPE})",
        title="Migration Result", border_style=border,
    ))

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Open Azure AI Foundry portal: https://ai.azure.com")
    console.print(f"  2. Find agent '{AGENT_NAME}' → Agents section → Playground")
    console.print("  3. Generate client code: oyd-migrator generate python")


if __name__ == "__main__":
    main()
