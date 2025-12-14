"""Command-line interface for prompt template tool."""

from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .registry import TemplateRegistry
from .template import Template, TemplateError

console = Console()


def get_registry() -> TemplateRegistry:
    """Get a template registry with default paths."""
    return TemplateRegistry()


@click.group()
@click.version_option(version="0.1.0", prog_name="prompt-template")
def cli() -> None:
    """Prompt Template - A tool for managing and rendering LLM prompts.

    Use 'prompt COMMAND --help' for more information on a command.
    """
    pass


@cli.command("list")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--search", "-s", help="Search by name or description")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--paths", is_flag=True, help="Show search paths status")
def list_templates(
    tags: tuple[str, ...],
    search: str | None,
    as_json: bool,
    paths: bool,
) -> None:
    """List available templates."""
    registry = get_registry()

    if paths:
        _show_search_paths(registry)
        return

    # Get templates with optional filtering
    if search or tags:
        templates = registry.search(query=search, tags=list(tags) if tags else None)
    else:
        templates = registry.list()

    if not templates:
        console.print("[yellow]No templates found.[/yellow]")
        console.print("\nSearch paths:")
        for status in registry.get_search_paths_status():
            if status["exists"]:
                exists = "[green]exists[/green]"
            else:
                exists = "[red]missing[/red]"
            console.print(f"  {status['path']} ({exists})")
        console.print("\nRun 'prompt init' to create a templates directory.")
        return

    if as_json:
        import json
        data = [
            {
                "name": t.name,
                "description": t.description,
                "version": t.version,
                "tags": t.tags,
                "path": str(t.path),
            }
            for t in templates
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title="Available Templates")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Description")
        table.add_column("Version", style="dim")
        table.add_column("Tags", style="green")

        for t in templates:
            desc = t.description
            if len(desc) > 50:
                desc = desc[:50] + "..."
            table.add_row(
                t.name,
                desc,
                t.version,
                ", ".join(t.tags) if t.tags else "",
            )

        console.print(table)


def _show_search_paths(registry: TemplateRegistry) -> None:
    """Show search paths and their status."""
    console.print("[bold]Template Search Paths:[/bold]\n")

    for status in registry.get_search_paths_status():
        if status["exists"]:
            console.print(f"  [green]✓[/green] {status['path']}")
        else:
            console.print(f"  [red]✗[/red] {status['path']} [dim](not found)[/dim]")


@cli.command("show")
@click.argument("name")
@click.option("--raw", is_flag=True, help="Show raw YAML content")
@click.option("--preview", is_flag=True, help="Show template preview with placeholders")
def show_template(name: str, raw: bool, preview: bool) -> None:
    """Show details of a template."""
    registry = get_registry()

    try:
        template = registry.load(name)
    except TemplateError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[yellow]Suggestion:[/yellow] {e.suggestion}")
        raise SystemExit(1)

    if raw:
        content = template.config.model_dump(by_alias=True, exclude_none=True)
        yaml_content = yaml.dump(content, default_flow_style=False, sort_keys=False)
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
        return

    # Show template details
    version_str = f"v{template.config.version}"
    console.print(Panel(f"[bold]{template.name}[/bold]", subtitle=version_str))

    if template.description:
        console.print(f"\n[dim]Description:[/dim] {template.description}")

    if template.config.tags:
        console.print(f"[dim]Tags:[/dim] {', '.join(template.config.tags)}")

    # Variables table
    if template.variables:
        console.print("\n[bold]Variables:[/bold]")
        var_table = Table(show_header=True, header_style="bold")
        var_table.add_column("Name")
        var_table.add_column("Type")
        var_table.add_column("Required")
        var_table.add_column("Default")
        var_table.add_column("Description")

        for var in template.variables:
            var_table.add_row(
                var.name,
                var.type.value,
                "Yes" if var.required else "No",
                str(var.default) if var.default is not None else "-",
                var.description or "-",
            )

        console.print(var_table)

    # Template content or preview
    console.print("\n[bold]Template:[/bold]")
    if preview:
        from rich.markup import escape
        preview_text = escape(template.preview())
        console.print(Panel(preview_text, title="Preview"))
    else:
        syntax = Syntax(
            template.template_content,
            "jinja2",
            theme="monokai",
            line_numbers=True,
        )
        console.print(syntax)


@cli.command("run")
@click.argument("name")
@click.option("--var", "-v", multiple=True, help="Variable in key=value format")
@click.option(
    "--json-input", "-j", type=click.File("r"), help="Load variables from JSON"
)
@click.option("--interactive", "-i", is_flag=True, help="Prompt for missing variables")
@click.option("--copy", "-c", is_flag=True, help="Copy result to clipboard")
def run_template(
    name: str,
    var: tuple[str, ...],
    json_input: Any,
    interactive: bool,
    copy: bool,
) -> None:
    """Render a template with variables."""
    registry = get_registry()

    try:
        template = registry.load(name)
    except TemplateError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[yellow]Suggestion:[/yellow] {e.suggestion}")
        raise SystemExit(1)

    # Collect variables
    variables: dict[str, Any] = {}

    # From JSON file
    if json_input:
        import json
        try:
            variables.update(json.load(json_input))
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing JSON:[/red] {e}")
            raise SystemExit(1)

    # From command line
    for v in var:
        if "=" not in v:
            console.print(f"[red]Invalid variable format:[/red] {v}")
            console.print("Use format: --var key=value")
            raise SystemExit(1)
        key, value = v.split("=", 1)
        variables[key] = value

    # Interactive mode - prompt for missing required variables
    if interactive:
        for var_config in template.variables:
            if var_config.name not in variables:
                if var_config.required and var_config.default is None:
                    prompt_text = f"{var_config.name}"
                    if var_config.description:
                        prompt_text += f" ({var_config.description})"

                    if var_config.enum:
                        opts = ", ".join(var_config.enum)
                        console.print(f"[dim]Options: {opts}[/dim]")

                    value = click.prompt(prompt_text)
                    variables[var_config.name] = value
                elif var_config.default is None:
                    # Optional without default - ask anyway
                    prompt_text = f"{var_config.name} (optional)"
                    value = click.prompt(prompt_text, default="", show_default=False)
                    if value:
                        variables[var_config.name] = value

    # Render template
    try:
        result = template.render(**variables)
    except TemplateError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[yellow]Suggestion:[/yellow] {e.suggestion}")
        raise SystemExit(1)

    # Output result
    console.print(Panel(result, title=f"Rendered: {name}"))

    # Copy to clipboard if requested
    if copy:
        try:
            import pyperclip
            pyperclip.copy(result)
            console.print("[green]Copied to clipboard![/green]")
        except ImportError:
            msg = "Install pyperclip for clipboard support: pip install pyperclip"
            console.print(f"[yellow]{msg}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Could not copy to clipboard: {e}[/yellow]")


@cli.command("validate")
@click.argument("file", type=click.Path(exists=True))
def validate_template(file: str) -> None:
    """Validate a template file."""
    try:
        template = Template.from_file(file)
        result = template.validate()

        if result.is_valid:
            console.print(f"[green]✓[/green] Template '{template.name}' is valid")
        else:
            console.print(f"[red]✗[/red] Template '{template.name}' has errors:")
            for error in result.errors:
                console.print(f"  [red]•[/red] {error}")

        if result.warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  [yellow]•[/yellow] {warning}")

        # Show summary
        num_defined = len(template.variables)
        num_used = len(template.get_all_variables())
        console.print(f"\n[dim]Variables defined: {num_defined}[/dim]")
        console.print(f"[dim]Variables used in template: {num_used}[/dim]")

        if not result.is_valid:
            raise SystemExit(1)

    except TemplateError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[yellow]Suggestion:[/yellow] {e.suggestion}")
        raise SystemExit(1)


@cli.command("init")
@click.option("--path", "-p", default="templates", help="Directory to create")
@click.option("--with-examples", is_flag=True, help="Include example templates")
def init_templates(path: str, with_examples: bool) -> None:
    """Initialize a templates directory."""
    templates_dir = Path(path)

    if templates_dir.exists():
        console.print(f"[yellow]Directory already exists:[/yellow] {templates_dir}")
        if not click.confirm("Add example templates?"):
            return
    else:
        templates_dir.mkdir(parents=True)
        console.print(f"[green]Created directory:[/green] {templates_dir}")

    if with_examples or not templates_dir.exists():
        _create_example_templates(templates_dir)


def _create_example_templates(directory: Path) -> None:
    """Create example templates in a directory."""
    examples = [
        {
            "filename": "summarizer.yaml",
            "content": {
                "name": "summarizer",
                "description": "Summarize text in different styles",
                "version": "1.0.0",
                "tags": ["summarization", "text"],
                "variables": [
                    {
                        "name": "text",
                        "type": "string",
                        "required": True,
                        "description": "The text to summarize",
                    },
                    {
                        "name": "style",
                        "type": "string",
                        "required": False,
                        "default": "bullet-points",
                        "enum": ["bullet-points", "paragraph", "one-liner"],
                        "description": "Summary style",
                    },
                    {
                        "name": "max_length",
                        "type": "integer",
                        "required": False,
                        "default": 200,
                        "description": "Maximum length in words",
                    },
                ],
                "template": """You are an expert summarizer.

Summarize the following text in {{style}} style.
Keep the summary under {{max_length}} words.

TEXT:
{{text}}

SUMMARY:""",
            },
        },
        {
            "filename": "code-reviewer.yaml",
            "content": {
                "name": "code-reviewer",
                "description": "Review code for issues and improvements",
                "version": "1.0.0",
                "tags": ["code", "review", "development"],
                "variables": [
                    {
                        "name": "code",
                        "type": "string",
                        "required": True,
                        "description": "The code to review",
                    },
                    {
                        "name": "language",
                        "type": "string",
                        "required": True,
                        "description": "Programming language",
                    },
                    {
                        "name": "focus",
                        "type": "string",
                        "required": False,
                        "default": "general",
                        "enum": ["general", "security", "performance", "readability"],
                        "description": "Review focus area",
                    },
                ],
                "template": """You are an expert {{language}} code reviewer.
Focus on: {{focus}}

Review the following code and provide:
1. Issues found (bugs, potential problems)
2. Suggestions for improvement
3. What's done well

CODE:
```{{language}}
{{code}}
```

REVIEW:""",
            },
        },
    ]

    for example in examples:
        filepath = directory / example["filename"]
        if not filepath.exists():
            with open(filepath, "w") as f:
                yaml.dump(
                    example["content"], f, default_flow_style=False, sort_keys=False
                )
            console.print(f"[green]Created:[/green] {filepath}")
        else:
            console.print(f"[dim]Skipped (exists):[/dim] {filepath}")


@cli.command("new")
@click.argument("name")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def new_template(name: str, output: str | None) -> None:
    """Create a new template interactively."""
    console.print(f"[bold]Creating new template: {name}[/bold]\n")

    description = click.prompt("Description", default="")

    # Collect variables
    variables = []
    console.print("\n[dim]Add variables (press Enter with empty name to finish):[/dim]")

    while True:
        var_name = click.prompt("Variable name", default="", show_default=False)
        if not var_name:
            break

        var_desc = click.prompt(f"  Description for '{var_name}'", default="")
        var_required = click.confirm(f"  Is '{var_name}' required?", default=True)
        var_default = None
        if not var_required:
            var_default = click.prompt(
                f"  Default value for '{var_name}'", default="", show_default=False
            )
            if not var_default:
                var_default = None

        variables.append({
            "name": var_name,
            "type": "string",
            "required": var_required,
            "description": var_desc,
            **({"default": var_default} if var_default else {}),
        })

    # Get template content
    console.print("\n[dim]Enter template content (opens editor):[/dim]")
    template_content = click.edit(
        "# Enter your template here\n# Use {{variable_name}} for variables\n"
    )

    if not template_content:
        console.print("[red]No template content provided. Aborting.[/red]")
        raise SystemExit(1)

    # Build template config
    config = {
        "name": name,
        "description": description,
        "version": "1.0.0",
        "tags": [],
        "variables": variables,
        "template": template_content.strip(),
    }

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = Path("templates") / f"{name}.yaml"
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save template
    with open(output_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    console.print(f"\n[green]Template saved to:[/green] {output_path}")

    # Validate the new template
    try:
        template = Template.from_file(output_path)
        result = template.validate()
        if result.is_valid:
            console.print("[green]✓ Template is valid[/green]")
        else:
            console.print("[yellow]⚠ Template has validation issues:[/yellow]")
            for error in result.errors:
                console.print(f"  {error}")
    except Exception as e:
        console.print(f"[yellow]⚠ Could not validate template: {e}[/yellow]")


if __name__ == "__main__":
    cli()
