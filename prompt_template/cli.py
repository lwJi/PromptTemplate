"""Command-line interface for prompt template tool."""

import glob
import json
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .formatters import get_formatter
from .registry import TemplateRegistry
from .template import Template, TemplateError

console = Console()


def handle_template_error(e: TemplateError) -> None:
    """Display template error and exit.

    Args:
        e: The TemplateError to display

    Raises:
        SystemExit: Always exits with code 1
    """
    console.print(f"[red]Error:[/red] {e.message}")
    if e.suggestion:
        console.print(f"[yellow]Suggestion:[/yellow] {e.suggestion}")
    raise SystemExit(1)


def load_file_content(file_path: str) -> str:
    """Load single file content with error handling.

    Args:
        file_path: Path to the file to load.

    Returns:
        File content as string.

    Raises:
        click.ClickException: If file cannot be read.
    """
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise click.ClickException(f"File not found: {file_path}")
    if not path.is_file():
        raise click.ClickException(f"Not a file: {file_path}")
    try:
        return path.read_text(encoding="utf-8")
    except PermissionError:
        raise click.ClickException(f"Permission denied: {file_path}")
    except UnicodeDecodeError:
        raise click.ClickException(f"Cannot read file (encoding error): {file_path}")


def load_files_content(pattern: str) -> str:
    """Load file(s) matching a path or glob pattern.

    For single files, returns the file content directly.
    For glob patterns matching multiple files, concatenates contents with headers.

    Args:
        pattern: File path or glob pattern (e.g., "*.py", "src/**/*.py").

    Returns:
        File content(s) as string.

    Raises:
        click.ClickException: If no files match or files cannot be read.
    """
    expanded = str(Path(pattern).expanduser())

    # Check if it's a glob pattern
    if any(c in pattern for c in "*?[]"):
        files = sorted(glob.glob(expanded, recursive=True))
        if not files:
            raise click.ClickException(f"No files match pattern: {pattern}")

        # Filter to only include actual files (not directories)
        files = [f for f in files if Path(f).is_file()]
        if not files:
            raise click.ClickException(f"No files match pattern: {pattern}")

        # Single file match - return content directly
        if len(files) == 1:
            return load_file_content(files[0])

        # Multiple files - concatenate with headers
        contents = []
        for file_path in files:
            content = load_file_content(file_path)
            contents.append(f"# File: {file_path}\n{content}")

        return "\n\n".join(contents)
    else:
        # Single file path
        return load_file_content(pattern)


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
        handle_template_error(e)

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
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["panel", "raw", "json", "markdown", "chat-api", "env"]),
    default="panel",
    help="Output format (default: panel)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Write output to file instead of stdout",
)
def run_template(
    name: str,
    var: tuple[str, ...],
    json_input: Any,
    interactive: bool,
    copy: bool,
    output_format: str,
    output: str | None,
) -> None:
    """Render a template with variables.

    Output formats:
      panel     Rich formatted panel (default, for terminal)
      raw       Plain text without decoration
      json      JSON with metadata
      markdown  Markdown formatted
      chat-api  OpenAI/Anthropic compatible messages format
      env       Shell environment variables
    """
    registry = get_registry()

    try:
        template = registry.load(name)
    except TemplateError as e:
        handle_template_error(e)

    # Collect variables
    variables: dict[str, Any] = {}

    # From JSON file
    if json_input:
        try:
            variables.update(json.load(json_input))
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing JSON:[/red] {e}")
            raise SystemExit(1)

    # From command line
    for v in var:
        if "=" not in v:
            console.print(f"[red]Invalid variable format:[/red] {v}")
            console.print("Use format: --var key=value or --var key=@file.txt")
            raise SystemExit(1)
        key, value = v.split("=", 1)

        # @ prefix: load file content
        if value.startswith("@"):
            file_pattern = value[1:]  # Remove @ prefix
            value = load_files_content(file_pattern)

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
        # Also get split prompts if available
        system_rendered, user_rendered = None, None
        if template.has_split_prompts:
            system_rendered, user_rendered = template.render_split(**variables)
    except TemplateError as e:
        handle_template_error(e)

    # Format output
    if output_format == "panel":
        # Rich panel format (default)
        formatted_output = None  # Will use console.print(Panel()) instead
    else:
        formatter = get_formatter(output_format)
        formatted_output = formatter.format(
            rendered=result,
            config=template.config,
            variables=variables,
            system_rendered=system_rendered,
            user_rendered=user_rendered,
        )

    # Output result
    if output:
        # Write to file
        output_path = Path(output)
        content = formatted_output if formatted_output else result
        output_path.write_text(content, encoding="utf-8")
        console.print(f"[green]Output written to:[/green] {output_path}")
    elif formatted_output:
        # Print formatted output (no Rich formatting)
        print(formatted_output)
    else:
        # Default panel format
        console.print(Panel(result, title=f"Rendered: {name}"))

    # Copy to clipboard if requested
    if copy:
        copy_content = formatted_output if formatted_output else result
        try:
            import pyperclip
            pyperclip.copy(copy_content)
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
        handle_template_error(e)


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
    examples: list[dict[str, Any]] = [
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


@cli.command("analyze")
@click.argument("name")
@click.option("--model", "-m", multiple=True, help="Target model(s) to check fit")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed analysis")
def analyze_template(
    name: str,
    model: tuple[str, ...],
    as_json: bool,
    verbose: bool,
) -> None:
    """Analyze template token usage and structure.

    Estimates token counts, checks model fit, and provides recommendations.

    Examples:

        prompt analyze summarizer

        prompt analyze summarizer -m gpt-4 -m claude-3-sonnet

        prompt analyze summarizer --verbose --json
    """
    from .analyzer import TemplateAnalyzer

    registry = get_registry()

    try:
        template = registry.load(name)
    except TemplateError as e:
        handle_template_error(e)

    analyzer = TemplateAnalyzer()
    target_models = list(model) if model else None
    result = analyzer.analyze(template.config, target_models=target_models)

    if as_json:
        output = {
            "template": result.template_name,
            "tokens": {
                "static": result.token_estimate.total_static_tokens,
                "estimated_total": result.token_estimate.estimated_total,
                "system_prompt": result.token_estimate.system_prompt_tokens,
                "user_prompt": result.token_estimate.user_prompt_tokens,
                "variables": result.token_estimate.estimated_variable_tokens,
            },
            "model_fit": result.token_estimate.model_fit,
            "structure": {
                "has_system_prompt": result.structural_analysis.has_system_prompt,
                "has_user_prompt": result.structural_analysis.has_user_prompt,
                "uses_conditionals": result.structural_analysis.uses_conditionals,
                "uses_loops": result.structural_analysis.uses_loops,
                "nesting_depth": result.structural_analysis.nesting_depth,
                "section_count": result.structural_analysis.section_count,
            },
            "recommendations": result.recommendations,
        }
        console.print(json.dumps(output, indent=2))
    else:
        # Rich formatted output
        console.print(Panel(f"[bold]Analysis: {result.template_name}[/bold]"))

        # Token table
        token_table = Table(title="Token Estimates")
        token_table.add_column("Component", style="cyan")
        token_table.add_column("Tokens", justify="right")

        if result.token_estimate.system_prompt_tokens:
            token_table.add_row(
                "System Prompt", str(result.token_estimate.system_prompt_tokens)
            )
        if result.token_estimate.user_prompt_tokens:
            token_table.add_row(
                "User Prompt", str(result.token_estimate.user_prompt_tokens)
            )
        if result.token_estimate.template_tokens:
            token_table.add_row("Template", str(result.token_estimate.template_tokens))

        token_table.add_row(
            "Static Total",
            str(result.token_estimate.total_static_tokens),
            style="bold",
        )
        token_table.add_row(
            "Estimated Total",
            str(result.token_estimate.estimated_total),
            style="bold green",
        )

        console.print(token_table)

        # Variable estimates
        if verbose and result.token_estimate.estimated_variable_tokens:
            var_table = Table(title="Variable Token Estimates")
            var_table.add_column("Variable")
            var_table.add_column("Est. Tokens", justify="right")

            var_tokens = result.token_estimate.estimated_variable_tokens
            for var_name, tokens in var_tokens.items():
                var_table.add_row(var_name, str(tokens))

            console.print(var_table)

        # Model fit
        if result.token_estimate.model_fit:
            console.print("\n[bold]Model Compatibility:[/bold]")
            for model_name, fits in result.token_estimate.model_fit.items():
                if fits:
                    status = "[green]✓ Fits[/green]"
                else:
                    status = "[red]✗ May exceed context[/red]"
                console.print(f"  {model_name}: {status}")

        # Structure info
        if verbose:
            console.print("\n[bold]Structure:[/bold]")
            s = result.structural_analysis
            has_split = "Yes" if s.has_system_prompt or s.has_user_prompt else "No"
            console.print(f"  System/User Split: {has_split}")
            cond = "Yes" if s.uses_conditionals else "No"
            console.print(f"  Uses Conditionals: {cond}")
            console.print(f"  Uses Loops: {'Yes' if s.uses_loops else 'No'}")
            console.print(f"  Nesting Depth: {s.nesting_depth}")
            console.print(f"  Section Count: {s.section_count}")

        # Recommendations
        if result.recommendations:
            console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            for rec in result.recommendations:
                console.print(f"  [yellow]•[/yellow] {rec}")


@cli.command("quality")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--brief", is_flag=True, help="Show only overall score")
def quality_report(name: str, as_json: bool, brief: bool) -> None:
    """Generate quality report for a template.

    Scores templates on clarity, consistency, completeness, efficiency, and structure.

    Examples:

        prompt quality summarizer

        prompt quality summarizer --brief

        prompt quality summarizer --json
    """
    from .quality import QualityScorer

    registry = get_registry()

    try:
        template = registry.load(name)
    except TemplateError as e:
        handle_template_error(e)

    scorer = QualityScorer()
    report = scorer.score(template.config)

    if as_json:
        output = {
            "template": report.template_name,
            "overall_score": report.overall_score,
            "grade": report.grade,
            "production_ready": report.is_production_ready,
            "dimensions": {
                dim.value: {
                    "score": score.score,
                    "details": score.details,
                    "suggestions": score.suggestions,
                }
                for dim, score in report.dimensions.items()
            },
            "summary": report.summary,
            "top_suggestions": report.top_suggestions,
        }
        console.print(json.dumps(output, indent=2))
    elif brief:
        grade_colors = {
            "A": "green",
            "B": "blue",
            "C": "yellow",
            "D": "red",
            "F": "red",
        }
        grade_color = grade_colors.get(report.grade, "white")
        score_str = f"{report.overall_score}/100 ({report.grade})"
        console.print(
            f"{report.template_name}: [{grade_color}]{score_str}[/{grade_color}]"
        )
    else:
        # Full report
        grade_colors = {
            "A": "green",
            "B": "blue",
            "C": "yellow",
            "D": "red",
            "F": "red",
        }
        grade_color = grade_colors.get(report.grade, "white")

        score_line = (
            f"Overall Score: [{grade_color}]{report.overall_score}/100"
            f"[/{grade_color}] (Grade: [{grade_color}]{report.grade}"
            f"[/{grade_color}])"
        )
        panel_content = (
            f"[bold]Quality Report: {report.template_name}[/bold]\n\n"
            f"{score_line}\n\n{report.summary}"
        )
        console.print(Panel(panel_content, title="Quality Assessment"))

        # Dimension scores
        dim_table = Table(title="Dimension Scores")
        dim_table.add_column("Dimension", style="cyan")
        dim_table.add_column("Score", justify="right")
        dim_table.add_column("Weight", justify="right", style="dim")
        dim_table.add_column("Key Finding")

        for dim, score in report.dimensions.items():
            # Color based on score
            if score.score >= 80:
                score_style = "green"
            elif score.score >= 60:
                score_style = "yellow"
            else:
                score_style = "red"

            finding = score.details[0] if score.details else "-"
            if len(finding) > 40:
                finding = finding[:40] + "..."
            dim_table.add_row(
                dim.value.title(),
                f"[{score_style}]{score.score}[/{score_style}]",
                f"{score.weight:.0%}",
                finding,
            )

        console.print(dim_table)

        # Top suggestions
        if report.top_suggestions:
            console.print("\n[bold]Top Suggestions:[/bold]")
            for i, suggestion in enumerate(report.top_suggestions, 1):
                console.print(f"  {i}. {suggestion}")

        # Production readiness
        if report.is_production_ready:
            console.print("\n[green]✓ Template is production-ready[/green]")
        else:
            console.print(
                "\n[yellow]⚠ Template needs improvement before production use[/yellow]"
            )


if __name__ == "__main__":
    cli()
