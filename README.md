# Prompt Template

A powerful prompt template tool for managing and rendering LLM prompts with Jinja2 support.

[![CI](https://github.com/lwJi/PromptTemplate/actions/workflows/ci.yml/badge.svg)](https://github.com/lwJi/PromptTemplate/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Features

- **Jinja2 Templating** - Full support for variables, conditionals, loops, and filters
- **YAML-based Templates** - Human-readable template format with metadata
- **Variable Validation** - Type checking, required/optional, defaults, and enum validation
- **Template Registry** - Discover and load templates from multiple paths
- **Rich CLI** - Beautiful command-line interface with syntax highlighting

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Initialize a templates directory

```bash
prompt init --with-examples
```

### 2. List available templates

```bash
prompt list
```

### 3. Show template details

```bash
prompt show summarizer
```

### 4. Run a template

```bash
prompt run summarizer -v "text=Your text here" -v "style=bullet-points"
```

Or interactively:

```bash
prompt run summarizer -i
```

## Template Format

Templates are YAML files with the following structure:

```yaml
name: my-template
description: A helpful description
version: 1.0.0
tags:
  - category
  - type

variables:
  - name: input_text
    type: string
    required: true
    description: The text to process

  - name: style
    type: string
    required: false
    default: formal
    enum: [formal, casual, technical]
    description: Output style

template: |
  You are a helpful assistant.

  {% if style == "formal" %}
  Please respond in a formal tone.
  {% else %}
  Feel free to be casual.
  {% endif %}

  Process the following:
  {{input_text}}
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `prompt list` | List available templates |
| `prompt show <name>` | Show template details |
| `prompt run <name>` | Render a template with variables |
| `prompt validate <file>` | Validate a template file |
| `prompt init` | Initialize templates directory |
| `prompt new <name>` | Create a new template interactively |

### Options

```bash
# List with filters
prompt list --tags summarization --search "text"

# Show with preview
prompt show summarizer --preview
prompt show summarizer --raw

# Run with variables
prompt run summarizer -v "text=Hello" -v "style=paragraph"
prompt run summarizer --json-input vars.json
prompt run summarizer -i  # Interactive mode
```

## Python API

```python
from prompt_template import Template, TemplateRegistry

# Load from file
template = Template.from_file("templates/summarizer.yaml")

# Or from dict
template = Template.from_dict({
    "name": "greeting",
    "template": "Hello, {{name}}!",
    "variables": [
        {"name": "name", "type": "string", "required": True}
    ]
})

# Render
result = template.render(name="World")
print(result)  # "Hello, World!"

# Validate
validation = template.validate()
if not validation.is_valid:
    print(validation.errors)

# Use registry
registry = TemplateRegistry()
template = registry.load("summarizer")
templates = registry.list()
```

## Variable Types

| Type | Python Type | Example |
|------|-------------|---------|
| `string` | `str` | `"hello"` |
| `integer` | `int` | `42` |
| `float` | `float` | `3.14` |
| `boolean` | `bool` | `true` |
| `list` | `list` | `["a", "b"]` |
| `object` | `dict` | `{"key": "value"}` |

## Template Syntax

This tool uses Jinja2 for templating. Common patterns:

```jinja2
{# Variables #}
Hello, {{name}}!

{# Conditionals #}
{% if formal %}
Dear {{name}},
{% else %}
Hey {{name}}!
{% endif %}

{# Loops #}
{% for item in items %}
- {{item}}
{% endfor %}

{# Filters #}
{{name | upper}}
{{items | length}}
{{value | default("N/A")}}
```

## Sample Templates

The tool includes sample templates:

- **summarizer** - Summarize text in different styles (bullet-points, paragraph, one-liner)
- **qa-assistant** - Answer questions with confidence levels and citations
- **code-reviewer** - Review code for issues, security, performance, or readability

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Run linting
ruff check prompt_template tests

# Run type checking
mypy prompt_template
```

## License

MIT
