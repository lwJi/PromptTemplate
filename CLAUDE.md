# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Commands

```bash
# Install
pip install -e ".[dev]"

# Test
pytest -v
pytest tests/test_template.py::TestTemplateRendering::test_simple_render -v

# Lint & Type Check
ruff check prompt_template tests
mypy prompt_template --ignore-missing-imports

# CLI
prompt list
prompt show <name>
prompt run <name> -v "var=value"
prompt run <name> -v "var=@file.txt"      # Load from file
prompt run <name> -v "var=@./src/*.py"    # Glob pattern
```

## Architecture

Jinja2 templating + Pydantic validation.

### Flow
1. YAML loaded via `Template.from_file()` or `TemplateRegistry`
2. Parsed into `TemplateConfig` (Pydantic)
3. `TemplateValidator` checks syntax and types
4. `TemplateRenderer` renders with Jinja2

### Components

- **`template.py`**: `Template` class - `from_file()`, `from_string()`, `from_dict()`, `render()`, `validate()`
- **`models.py`**: Pydantic models - `TemplateConfig`, `VariableConfig`, `VariableType`
- **`renderer.py`**: `TemplateRenderer` - Jinja2 wrapper
- **`validator.py`**: `TemplateValidator` - syntax, types, unused/undeclared vars
- **`registry.py`**: `TemplateRegistry` - discovers from `./templates`, `./prompts`, `~/.prompt_templates`
- **`cli.py`**: Click CLI with Rich - `list`, `show`, `run`, `validate`, `init`, `new`; file input via `@` prefix

### YAML Schema
```yaml
name: string (required)
description: string
version: string
tags: [string]
variables:
  - name: string (required)
    type: string|integer|float|boolean|list|object
    required: boolean
    default: any
    enum: [values]
    description: string
template: string (required)
```
