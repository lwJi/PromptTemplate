"""Output formatters for rendered templates."""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from .models import TemplateConfig


class OutputFormatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format(
        self,
        rendered: str,
        config: TemplateConfig,
        variables: dict[str, Any],
        system_rendered: str | None = None,
        user_rendered: str | None = None,
    ) -> str:
        """Format the rendered template output.

        Args:
            rendered: The fully rendered template (or combined system+user)
            config: The template configuration
            variables: Variables used for rendering
            system_rendered: Rendered system prompt (if using split prompts)
            user_rendered: Rendered user prompt (if using split prompts)

        Returns:
            Formatted output string
        """
        pass


class RawFormatter(OutputFormatter):
    """Plain text output without any decoration."""

    def format(
        self,
        rendered: str,
        config: TemplateConfig,
        variables: dict[str, Any],
        system_rendered: str | None = None,
        user_rendered: str | None = None,
    ) -> str:
        """Return raw rendered content."""
        return rendered


class JSONFormatter(OutputFormatter):
    """JSON output with metadata."""

    def __init__(self, indent: int = 2) -> None:
        self.indent = indent

    def format(
        self,
        rendered: str,
        config: TemplateConfig,
        variables: dict[str, Any],
        system_rendered: str | None = None,
        user_rendered: str | None = None,
    ) -> str:
        """Return JSON formatted output with metadata."""
        output: dict[str, Any] = {
            "template": {
                "name": config.name,
                "version": config.version,
                "description": config.description,
            },
            "rendered": rendered,
            "variables": variables,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Add split prompts if available
        if system_rendered is not None or user_rendered is not None:
            output["prompts"] = {}
            if system_rendered is not None:
                output["prompts"]["system"] = system_rendered
            if user_rendered is not None:
                output["prompts"]["user"] = user_rendered

        return json.dumps(output, indent=self.indent, ensure_ascii=False)


class MarkdownFormatter(OutputFormatter):
    """Markdown formatted output."""

    def format(
        self,
        rendered: str,
        config: TemplateConfig,
        variables: dict[str, Any],
        system_rendered: str | None = None,
        user_rendered: str | None = None,
    ) -> str:
        """Return Markdown formatted output."""
        lines = [
            f"# {config.name}",
            "",
            f"**Version:** {config.version}",
        ]

        if config.description:
            lines.append(f"**Description:** {config.description}")

        lines.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
        lines.append("")

        # Variables section
        if variables:
            lines.append("## Variables")
            lines.append("")
            lines.append("| Variable | Value |")
            lines.append("|----------|-------|")
            for key, value in variables.items():
                # Truncate long values
                val_str = str(value)
                if len(val_str) > 50:
                    val_str = val_str[:47] + "..."
                # Escape pipe characters
                val_str = val_str.replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {key} | {val_str} |")
            lines.append("")

        # Output section(s)
        if system_rendered is not None or user_rendered is not None:
            if system_rendered:
                lines.append("## System Prompt")
                lines.append("")
                lines.append(system_rendered)
                lines.append("")
            if user_rendered:
                lines.append("## User Prompt")
                lines.append("")
                lines.append(user_rendered)
                lines.append("")
        else:
            lines.append("## Rendered Output")
            lines.append("")
            lines.append(rendered)

        return "\n".join(lines)


class ChatAPIFormatter(OutputFormatter):
    """OpenAI/Anthropic compatible chat API format."""

    def __init__(self, provider: str = "openai") -> None:
        """Initialize with provider hint.

        Args:
            provider: API provider ("openai" or "anthropic")
        """
        self.provider = provider

    def format(
        self,
        rendered: str,
        config: TemplateConfig,
        variables: dict[str, Any],
        system_rendered: str | None = None,
        user_rendered: str | None = None,
    ) -> str:
        """Return chat API formatted output."""
        messages: list[dict[str, str]] = []

        if system_rendered is not None or user_rendered is not None:
            # Use split prompts
            if system_rendered:
                messages.append({"role": "system", "content": system_rendered})
            if user_rendered:
                messages.append({"role": "user", "content": user_rendered})
        else:
            # Single template - treat as user message
            # If it looks like it has a system instruction, try to split
            messages.append({"role": "user", "content": rendered})

        output: dict[str, Any] = {
            "messages": messages,
            "metadata": {
                "template": config.name,
                "version": config.version,
                "provider_hint": self.provider,
            },
        }

        return json.dumps(output, indent=2, ensure_ascii=False)


class EnvFormatter(OutputFormatter):
    """Shell environment variable format."""

    def format(
        self,
        rendered: str,
        config: TemplateConfig,
        variables: dict[str, Any],
        system_rendered: str | None = None,
        user_rendered: str | None = None,
    ) -> str:
        """Return shell environment variable format."""
        lines = [
            "#!/bin/bash",
            f"# Template: {config.name} v{config.version}",
            f"# Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            f'export PROMPT_TEMPLATE_NAME="{config.name}"',
            f'export PROMPT_TEMPLATE_VERSION="{config.version}"',
            "",
        ]

        # Export variables
        for key, value in variables.items():
            # Escape single quotes for shell
            val_str = str(value).replace("'", "'\\''")
            lines.append(f"export PROMPT_VAR_{key.upper()}='{val_str}'")

        lines.append("")

        # Export the rendered content using heredoc for multiline
        lines.append("read -r -d '' PROMPT_CONTENT << 'PROMPT_EOF'")
        lines.append(rendered)
        lines.append("PROMPT_EOF")
        lines.append("export PROMPT_CONTENT")

        if system_rendered is not None:
            lines.append("")
            lines.append("read -r -d '' PROMPT_SYSTEM << 'PROMPT_EOF'")
            lines.append(system_rendered)
            lines.append("PROMPT_EOF")
            lines.append("export PROMPT_SYSTEM")

        if user_rendered is not None:
            lines.append("")
            lines.append("read -r -d '' PROMPT_USER << 'PROMPT_EOF'")
            lines.append(user_rendered)
            lines.append("PROMPT_EOF")
            lines.append("export PROMPT_USER")

        return "\n".join(lines)


# Format name to formatter class mapping
FORMATTERS: dict[str, type[OutputFormatter]] = {
    "raw": RawFormatter,
    "json": JSONFormatter,
    "markdown": MarkdownFormatter,
    "chat-api": ChatAPIFormatter,
    "env": EnvFormatter,
}


def get_formatter(format_name: str) -> OutputFormatter:
    """Get a formatter instance by name.

    Args:
        format_name: Name of the format (raw, json, markdown, chat-api, env)

    Returns:
        OutputFormatter instance

    Raises:
        ValueError: If format name is not recognized
    """
    if format_name not in FORMATTERS:
        valid = ", ".join(FORMATTERS.keys())
        raise ValueError(f"Unknown format '{format_name}'. Valid formats: {valid}")

    return FORMATTERS[format_name]()
