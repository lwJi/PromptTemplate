# Prompt Template

A prompt template tool for managing and rendering LLM prompts with Jinja2 support.

[![CI](https://github.com/lwJi/PromptTemplate/actions/workflows/ci.yml/badge.svg)](https://github.com/lwJi/PromptTemplate/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Features

- **Jinja2 Templating** - Variables, conditionals, loops, and filters
- **YAML-based Templates** - Human-readable format with metadata
- **Variable Validation** - Type checking, defaults, and enum constraints
- **Template Registry** - Auto-discover templates from `./templates`, `./prompts`, `~/.prompt_templates`
- **Rich CLI** - Syntax highlighting and interactive mode

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Initialize with examples
prompt init --with-examples

# List templates
prompt list

# Show template details
prompt show summarizer

# Run a template
prompt run summarizer -v "text=Your text here" -v "style=bullet-points"

# Interactive mode
prompt run summarizer -i
```

## Template Format

```yaml
name: my-template
description: A helpful description
version: 1.0.0
tags: [category, type]

variables:
  - name: input_text
    type: string
    required: true
    description: The text to process

  - name: style
    type: string
    default: formal
    enum: [formal, casual, technical]

template: |
  {% if style == "formal" %}
  Please respond formally.
  {% endif %}

  Process: {{input_text}}
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `prompt list` | List available templates |
| `prompt show <name>` | Show template details |
| `prompt run <name>` | Render a template |
| `prompt validate <file>` | Validate a template file |
| `prompt init` | Initialize templates directory |
| `prompt new <name>` | Create a new template |

## Python API

```python
from prompt_template import Template, TemplateRegistry

# Load and render
template = Template.from_file("templates/summarizer.yaml")
result = template.render(text="Hello", style="paragraph")

# Validate
validation = template.validate()
if not validation.is_valid:
    print(validation.errors)

# Use registry
registry = TemplateRegistry()
template = registry.load("summarizer")
```

## Variable Types

| Type | Python Type |
|------|-------------|
| `string` | `str` |
| `integer` | `int` |
| `float` | `float` |
| `boolean` | `bool` |
| `list` | `list` |
| `object` | `dict` |

## Development

```bash
pip install -e ".[dev]"
pytest -v
ruff check prompt_template tests
mypy prompt_template --ignore-missing-imports
```

## License

MIT
