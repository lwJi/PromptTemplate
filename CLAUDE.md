# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install package with dev dependencies
pip install -e ".[dev]"

# Run all tests with coverage
pytest -v

# Run a single test file
pytest tests/test_template.py -v

# Run a specific test
pytest tests/test_template.py::TestTemplateRendering::test_simple_render -v

# Linting
ruff check prompt_template tests

# Type checking
mypy prompt_template --ignore-missing-imports

# CLI usage after install
prompt list
prompt show <template-name>
prompt run <template-name> -v "var=value"
```

## Architecture

This is a prompt template management tool that uses Jinja2 for templating and Pydantic for validation.

### Core Flow
1. Templates are YAML files loaded via `Template.from_file()` or discovered by `TemplateRegistry`
2. YAML is parsed into `TemplateConfig` (Pydantic model) for validation
3. `TemplateValidator` checks syntax, variable declarations, and type constraints
4. `TemplateRenderer` uses Jinja2 to render templates with provided variables

### Key Components

- **`template.py`**: `Template` class - main entry point for loading, validating, and rendering templates. Factory methods: `from_file()`, `from_string()`, `from_dict()`

- **`models.py`**: Pydantic models (`TemplateConfig`, `VariableConfig`, `VariableType`) defining the YAML schema

- **`renderer.py`**: `TemplateRenderer` - wraps Jinja2 with strict undefined handling and variable extraction

- **`validator.py`**: `TemplateValidator` - validates syntax, type checking, enum constraints, detects unused/undeclared variables

- **`registry.py`**: `TemplateRegistry` - discovers templates from search paths (`./templates`, `./prompts`, `~/.prompt_templates`)

- **`cli.py`**: Click-based CLI with Rich output (`list`, `show`, `run`, `validate`, `init`, `new` commands)

### Template YAML Schema
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
template: string (Jinja2 content, required)
model_config: {provider, model, parameters}  # optional
```
