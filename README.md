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
- **Multiple Output Formats** - Raw, JSON, Markdown, Chat API, shell env
- **LLM-Ready** - System/user prompt separation for chat APIs
- **Token Analysis** - Estimate token usage with model fit checking
- **Quality Scoring** - A-F grades with actionable improvement suggestions
- **Semantic Validation** - Check role clarity, instruction quality, and coherence

## Installation

```bash
pip install -e .

# With tiktoken for accurate token counting
pip install -e ".[analysis]"
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

# Load variable from file using @ prefix
prompt run code-reviewer -v "code=@./src/main.py" -v "language=python"

# Load multiple files using glob patterns
prompt run code-reviewer -v "code=@./src/*.py"

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
| `prompt analyze <name>` | Analyze token usage and structure |
| `prompt quality <name>` | Score template quality (A-F grade) |
| `prompt init` | Initialize templates directory |
| `prompt new <name>` | Create a new template |

## File Input

Load file contents as variable values using the `@` prefix:

```bash
# Single file
prompt run template -v "content=@./file.txt"

# Glob pattern (multiple files)
prompt run template -v "code=@./src/*.py"

# Recursive glob
prompt run template -v "code=@./src/**/*.py"
```

When multiple files match a glob pattern, they are concatenated with `# File: <path>` headers.

## Output Formats

Use `--format` / `-f` to specify output format:

```bash
# Raw text (for piping)
prompt run template -v "text=hello" -f raw

# JSON with metadata (for automation)
prompt run template -v "text=hello" -f json

# Markdown (for documentation)
prompt run template -v "text=hello" -f markdown

# OpenAI/Anthropic chat API format
prompt run template -v "text=hello" -f chat-api

# Shell environment variables
prompt run template -v "text=hello" -f env

# Write to file
prompt run template -v "text=hello" -f json -o output.json
```

## System/User Prompts

For chat APIs, separate system and user prompts:

```yaml
name: assistant
system_prompt: |
  You are a helpful {{role}}.
user_prompt: |
  Help me with: {{task}}
variables:
  - name: role
    type: string
    required: true
  - name: task
    type: string
    required: true
```

Use with `chat-api` format for OpenAI/Anthropic compatible output:

```bash
prompt run assistant -v "role=coding assistant" -v "task=debugging" -f chat-api
```

Output:
```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful coding assistant."},
    {"role": "user", "content": "Help me with: debugging"}
  ]
}
```

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

## Template Analysis

Analyze token usage and check model compatibility:

```bash
# Analyze a template
prompt analyze summarizer

# JSON output for automation
prompt analyze summarizer --json
```

Analysis includes:
- Token counts (static and estimated variable tokens)
- Model fit checking (GPT-4, GPT-4-turbo, Claude-3, etc.)
- Structural analysis (conditionals, loops, sections)
- Variable usage tracking

## Quality Scoring

Score templates and get improvement suggestions:

```bash
# Score a template
prompt quality code-reviewer

# JSON output
prompt quality code-reviewer --json
```

Quality dimensions:
- **Clarity** (25%) - Role definition, task instructions, output format
- **Completeness** (25%) - Description, variable docs, metadata
- **Consistency** (20%) - Naming conventions, style uniformity
- **Efficiency** (15%) - Token economy, no redundancy
- **Structure** (15%) - Prompt organization, separation of concerns

Grades: A (90+), B (80+), C (70+), D (60+), F (<60). Templates scoring 70+ are considered production-ready.

## Development

```bash
pip install -e ".[dev]"
pytest -v
ruff check prompt_template tests
mypy prompt_template --ignore-missing-imports
```

## License

MIT
