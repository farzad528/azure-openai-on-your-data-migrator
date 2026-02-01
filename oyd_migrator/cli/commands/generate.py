"""Code generation and report commands."""

from pathlib import Path
from typing import Optional, Literal

import typer
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich import box

from oyd_migrator.core.constants import Display
from oyd_migrator.core.logging import get_logger

app = typer.Typer(help="Generate code samples and reports.")
console = Console()
logger = get_logger("generate")


@app.command("comparison")
def comparison_command(
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path. If not specified, prints to console.",
    ),
    format: Literal["table", "markdown", "json"] = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format.",
    ),
) -> None:
    """
    Generate the feature comparison matrix.

    Shows a detailed comparison between:
    - Azure OpenAI On Your Data (OYD) - Deprecated
    - Foundry Agent Service with Azure AI Search Tool
    - Foundry Agent Service with Foundry IQ Knowledge Base
    """
    # Feature comparison data
    features = [
        ("Azure AI Search", True, True, True),
        ("Semantic Search", True, True, True),
        ("Vector Search", True, True, True),
        ("Hybrid Search", True, True, True),
        ("Multi-Index Support", False, True, True),
        ("Multi-Source Types", "Limited", True, True),
        ("Citations", True, True, True),
        ("Managed Identity", True, True, True),
        ("VNet/Private Endpoints", True, "Standard", "Standard"),
        ("Document ACLs", "Entra groups", "filter param", "ACL header"),
        ("Multi-turn Conversations", False, True, True),
        ("Tool Orchestration", False, True, True),
        ("Code Interpreter", False, True, True),
        ("Query Decomposition", False, False, True),
        ("Agentic Reasoning", False, "Basic", "Full"),
        ("Streaming", True, True, True),
        ("Supported Models", "GPT-4o (retiring)", "GPT-4.1+", "GPT-4.1+"),
        ("API Status", "Deprecated", "GA", "Preview"),
    ]

    def bool_to_str(val):
        if isinstance(val, bool):
            return Display.SUCCESS if val else Display.FAILURE
        return str(val)

    if format == "table":
        table = Table(
            title="OYD vs Foundry Agent Service Feature Comparison",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Feature", style="white")
        table.add_column("OYD (Deprecated)", justify="center")
        table.add_column("Foundry + Search Tool", justify="center")
        table.add_column("Foundry + IQ KB", justify="center")

        for feature, oyd, search_tool, kb in features:
            table.add_row(
                feature,
                bool_to_str(oyd),
                bool_to_str(search_tool),
                bool_to_str(kb),
            )

        console.print()
        console.print(table)
        console.print()
        console.print("[bold]Legend:[/bold]")
        console.print(f"  {Display.SUCCESS} = Supported")
        console.print(f"  {Display.FAILURE} = Not Supported")
        console.print("  Standard = Requires Standard deployment (for VNet)")
        console.print()
        console.print("[bold]Recommendations:[/bold]")
        console.print("  • For simple RAG with existing indexes: [cyan]Foundry + Azure AI Search Tool[/cyan]")
        console.print("  • For complex reasoning and multi-source: [cyan]Foundry + Foundry IQ Knowledge Base[/cyan]")
        console.print()

    elif format == "markdown":
        md_content = """# OYD vs Foundry Agent Service Feature Comparison

| Feature | OYD (Deprecated) | Foundry + Search Tool | Foundry + IQ KB |
|---------|------------------|----------------------|-----------------|
"""
        for feature, oyd, search_tool, kb in features:
            def md_val(val):
                if isinstance(val, bool):
                    return "✅" if val else "❌"
                return str(val)
            md_content += f"| {feature} | {md_val(oyd)} | {md_val(search_tool)} | {md_val(kb)} |\n"

        md_content += """
## Recommendations

- **For simple RAG with existing indexes**: Use Foundry + Azure AI Search Tool
- **For complex reasoning and multi-source**: Use Foundry + Foundry IQ Knowledge Base

## Migration Paths

### Path A: Azure AI Search Tool
- Direct index connection via `AzureAISearchAgentTool`
- Simpler setup, familiar query patterns
- Best for straightforward RAG scenarios

### Path B: Foundry IQ Knowledge Base
- MCP-based with `knowledge_base_retrieve` tool
- Advanced query planning and decomposition
- Better for complex reasoning scenarios
"""

        if output:
            output.write_text(md_content)
            console.print(f"{Display.SUCCESS} Feature comparison saved to: {output}")
        else:
            console.print(Markdown(md_content))

    elif format == "json":
        import json
        data = {
            "features": [
                {
                    "name": f[0],
                    "oyd": f[1],
                    "foundry_search_tool": f[2],
                    "foundry_iq_kb": f[3],
                }
                for f in features
            ]
        }
        if output:
            output.write_text(json.dumps(data, indent=2))
            console.print(f"{Display.SUCCESS} Feature comparison saved to: {output}")
        else:
            console.print(json.dumps(data, indent=2))


@app.command("python")
def python_command(
    agent_name: str = typer.Argument(
        ...,
        help="Name of the agent to generate code for.",
    ),
    project_endpoint: str = typer.Option(
        ...,
        "--project-endpoint",
        "-p",
        help="Foundry project endpoint URL.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path.",
    ),
) -> None:
    """
    Generate Python SDK sample code for an agent.

    Creates a ready-to-run Python script demonstrating how to use
    the migrated agent with the Azure AI Projects SDK.
    """
    from oyd_migrator.generators.sdk_samples import generate_python_sample

    console.print(f"\n{Display.INFO} Generating Python SDK sample for: [cyan]{agent_name}[/cyan]\n")

    try:
        code = generate_python_sample(
            agent_name=agent_name,
            project_endpoint=project_endpoint,
        )

        if output:
            output.write_text(code)
            console.print(f"{Display.SUCCESS} Python sample saved to: {output}")
        else:
            from rich.syntax import Syntax
            syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
            console.print(syntax)

    except Exception as e:
        logger.exception("Code generation failed")
        console.print(f"{Display.FAILURE} Generation failed: {e}")
        raise typer.Exit(1)


@app.command("curl")
def curl_command(
    agent_name: str = typer.Argument(
        ...,
        help="Name of the agent to generate commands for.",
    ),
    project_endpoint: str = typer.Option(
        ...,
        "--project-endpoint",
        "-p",
        help="Foundry project endpoint URL.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path.",
    ),
) -> None:
    """
    Generate cURL command examples for an agent.

    Creates shell commands demonstrating how to call the agent
    using the REST API directly.
    """
    from oyd_migrator.generators.curl_samples import generate_curl_commands

    console.print(f"\n{Display.INFO} Generating cURL commands for: [cyan]{agent_name}[/cyan]\n")

    try:
        commands = generate_curl_commands(
            agent_name=agent_name,
            project_endpoint=project_endpoint,
        )

        if output:
            output.write_text(commands)
            console.print(f"{Display.SUCCESS} cURL commands saved to: {output}")
        else:
            from rich.syntax import Syntax
            syntax = Syntax(commands, "bash", theme="monokai")
            console.print(syntax)

    except Exception as e:
        logger.exception("Code generation failed")
        console.print(f"{Display.FAILURE} Generation failed: {e}")
        raise typer.Exit(1)


@app.command("report")
def report_command(
    session_id: str = typer.Argument(
        ...,
        help="Migration session ID to generate report for.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path.",
    ),
    format: Literal["markdown", "html", "json"] = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Report format.",
    ),
) -> None:
    """
    Generate a migration report for a completed session.

    Creates a detailed report including:
    - Resources migrated
    - Test results
    - Configuration details
    - Next steps
    """
    from oyd_migrator.core.config import get_settings, MigrationState
    from oyd_migrator.generators.migration_report import generate_report

    console.print(f"\n{Display.INFO} Generating migration report for session: [cyan]{session_id}[/cyan]\n")

    try:
        settings = get_settings()
        state = MigrationState.load(session_id, settings.config_dir)

        if not state:
            console.print(f"{Display.FAILURE} Session '{session_id}' not found.")
            raise typer.Exit(1)

        report = generate_report(state, format=format)

        if output:
            output.write_text(report)
            console.print(f"{Display.SUCCESS} Report saved to: {output}")
        else:
            if format == "markdown":
                console.print(Markdown(report))
            else:
                console.print(report)

    except Exception as e:
        logger.exception("Report generation failed")
        console.print(f"{Display.FAILURE} Generation failed: {e}")
        raise typer.Exit(1)
