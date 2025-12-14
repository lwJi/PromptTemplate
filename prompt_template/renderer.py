"""Jinja2-based template renderer."""

import re
from typing import Any

from jinja2 import (
    StrictUndefined,
    TemplateSyntaxError,
    UndefinedError,
    meta,
)
from jinja2.sandbox import SandboxedEnvironment


class TemplateRenderer:
    """Renders templates using Jinja2."""

    def __init__(self, autoescape: bool = False) -> None:
        """Initialize the renderer with a Jinja2 environment.

        Args:
            autoescape: Whether to autoescape HTML (default False for prompts)
        """
        # Use SandboxedEnvironment to prevent template injection attacks
        self.env = SandboxedEnvironment(
            autoescape=autoescape,
            # Use StrictUndefined to raise errors for undefined variables
            undefined=StrictUndefined,
        )

    def render(self, template_string: str, variables: dict[str, Any]) -> str:
        """Render a template with the given variables.

        Args:
            template_string: The Jinja2 template string
            variables: Dictionary of variable values

        Returns:
            The rendered template string

        Raises:
            TemplateSyntaxError: If template syntax is invalid
            UndefinedError: If required variables are missing
        """
        template = self.env.from_string(template_string)
        return template.render(**variables)

    def extract_variables(self, template_string: str) -> set[str]:
        """Extract all variable names from a template.

        Args:
            template_string: The Jinja2 template string

        Returns:
            Set of variable names found in the template
        """
        try:
            ast = self.env.parse(template_string)
            return meta.find_undeclared_variables(ast)
        except TemplateSyntaxError:
            # Fall back to regex for invalid templates
            return self._extract_variables_regex(template_string)

    def _extract_variables_regex(self, template_string: str) -> set[str]:
        """Extract variables using regex (fallback method).

        Args:
            template_string: The template string

        Returns:
            Set of variable names found
        """
        # Match {{ variable }} and {{ variable.attr }} patterns
        pattern = r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)"
        matches = re.findall(pattern, template_string)
        return set(matches)

    def validate_syntax(self, template_string: str) -> list[str]:
        """Validate template syntax.

        Args:
            template_string: The template string to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors: list[str] = []

        try:
            self.env.parse(template_string)
        except TemplateSyntaxError as e:
            errors.append(f"Syntax error: {e.message}")
            if e.lineno:
                errors.append(f"  at line {e.lineno}")

        # Check for unbalanced braces
        open_braces = template_string.count("{{")
        close_braces = template_string.count("}}")
        if open_braces != close_braces:
            errors.append(
                f"Unbalanced braces: {open_braces} opening '{{{{' vs "
                f"{close_braces} closing '}}}}'"
            )

        # Check for common mistakes
        if "{%" in template_string:
            open_blocks = template_string.count("{%")
            close_blocks = template_string.count("%}")
            if open_blocks != close_blocks:
                errors.append(
                    f"Unbalanced block tags: {open_blocks} opening '{{% ' vs "
                    f"{close_blocks} closing ' %}}'"
                )

        return errors

    def preview(
        self, template_string: str, variables: dict[str, Any] | None = None
    ) -> str:
        """Preview a template with optional variables.

        Missing variables are shown as placeholders.

        Args:
            template_string: The template string
            variables: Optional variable values

        Returns:
            Preview of the rendered template
        """
        if variables is None:
            variables = {}

        # Get all variables in template
        template_vars = self.extract_variables(template_string)

        # Create preview dict with placeholders for missing vars
        preview_vars = dict(variables)
        for var in template_vars:
            if var not in preview_vars:
                preview_vars[var] = f"[{var}]"

        try:
            # Use a lenient sandboxed environment for preview
            lenient_env = SandboxedEnvironment(autoescape=False)
            template = lenient_env.from_string(template_string)
            return template.render(**preview_vars)
        except TemplateSyntaxError as e:
            return f"Preview error (syntax): {e.message}"
        except UndefinedError as e:
            return f"Preview error (undefined variable): {e}"
        except Exception as e:
            return f"Preview error: {e}"
