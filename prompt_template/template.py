"""Core Template class for loading, validating, and rendering templates."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import TemplateConfig, VariableConfig
from .renderer import TemplateRenderer
from .validator import TemplateValidator, ValidationResult


class TemplateError(Exception):
    """Base exception for template errors."""

    def __init__(
        self,
        message: str,
        suggestion: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Error message
            suggestion: Optional suggestion for fixing the error
            context: Optional context information
        """
        self.message = message
        self.suggestion = suggestion
        self.context = context or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with suggestion and context."""
        parts = [self.message]

        if self.suggestion:
            parts.append(f"\nSuggestion: {self.suggestion}")

        if self.context:
            parts.append("\nContext:")
            for key, value in self.context.items():
                parts.append(f"  {key}: {value}")

        return "".join(parts)


class TemplateNotFoundError(TemplateError):
    """Raised when a template file cannot be found."""

    pass


class TemplateValidationError(TemplateError):
    """Raised when template validation fails."""

    pass


class TemplateRenderError(TemplateError):
    """Raised when template rendering fails."""

    pass


class Template:
    """A prompt template that can be loaded, validated, and rendered."""

    def __init__(self, config: TemplateConfig) -> None:
        """Initialize a template with configuration.

        Args:
            config: The template configuration
        """
        self.config = config
        self._renderer = TemplateRenderer()
        self._validator = TemplateValidator()

    @classmethod
    def from_file(cls, path: str | Path) -> "Template":
        """Load a template from a YAML or JSON file.

        Args:
            path: Path to the template file

        Returns:
            Template instance

        Raises:
            TemplateNotFoundError: If file doesn't exist
            TemplateValidationError: If file content is invalid
        """
        path = Path(path)

        if not path.exists():
            raise TemplateNotFoundError(
                f"Template file not found: {path}",
                suggestion="Check the file path and ensure the file exists",
                context={"path": str(path.absolute())},
            )

        try:
            content = path.read_text(encoding="utf-8")
        except IOError as e:
            raise TemplateError(
                f"Failed to read template file: {e}",
                context={"path": str(path)},
            )

        return cls.from_string(content, source=str(path))

    @classmethod
    def from_string(cls, content: str, source: str = "<string>") -> "Template":
        """Load a template from a YAML/JSON string.

        Args:
            content: YAML or JSON content
            source: Source identifier for error messages

        Returns:
            Template instance

        Raises:
            TemplateValidationError: If content is invalid
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise TemplateValidationError(
                f"Failed to parse YAML: {e}",
                suggestion="Check YAML syntax and indentation",
                context={"source": source},
            )

        if not isinstance(data, dict):
            raise TemplateValidationError(
                "Template must be a YAML dictionary/object",
                suggestion="Ensure template starts with key-value pairs, not a list",
                context={"source": source, "got_type": type(data).__name__},
            )

        return cls.from_dict(data, source=source)

    @classmethod
    def from_dict(cls, data: dict[str, Any], source: str = "<dict>") -> "Template":
        """Create a template from a dictionary.

        Args:
            data: Dictionary with template configuration
            source: Source identifier for error messages

        Returns:
            Template instance

        Raises:
            TemplateValidationError: If data is invalid
        """
        try:
            config = TemplateConfig(**data)
        except ValidationError as e:
            errors = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                errors.append(f"  {loc}: {err['msg']}")

            raise TemplateValidationError(
                f"Invalid template configuration:\n" + "\n".join(errors),
                context={"source": source},
            )

        return cls(config)

    @property
    def name(self) -> str:
        """Get the template name."""
        return self.config.name

    @property
    def description(self) -> str:
        """Get the template description."""
        return self.config.description

    @property
    def variables(self) -> list[VariableConfig]:
        """Get the template variables."""
        return self.config.variables

    @property
    def template_content(self) -> str:
        """Get the raw template content."""
        return self.config.template

    def validate(self) -> ValidationResult:
        """Validate the template configuration.

        Returns:
            ValidationResult with errors and warnings
        """
        return self._validator.validate(self.config)

    def render(self, **variables: Any) -> str:
        """Render the template with the given variables.

        Args:
            **variables: Variable values to substitute

        Returns:
            The rendered template string

        Raises:
            TemplateRenderError: If rendering fails
        """
        # Apply defaults for missing optional variables
        merged_vars = self._apply_defaults(variables)

        # Validate inputs
        validation = self._validator.validate_inputs(self.config, merged_vars)
        if not validation.is_valid:
            raise TemplateRenderError(
                f"Invalid input values:\n  " + "\n  ".join(validation.errors),
                context={"provided_vars": list(variables.keys())},
            )

        try:
            return self._renderer.render(self.config.template, merged_vars)
        except Exception as e:
            raise TemplateRenderError(
                f"Failed to render template: {e}",
                suggestion="Check that all required variables are provided",
                context={"variables": list(merged_vars.keys())},
            )

    def _apply_defaults(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Apply default values for missing variables.

        Args:
            variables: Provided variable values

        Returns:
            Variables with defaults applied
        """
        merged = dict(variables)

        for var in self.config.variables:
            if var.name not in merged and var.default is not None:
                merged[var.name] = var.default

        return merged

    def preview(self, **variables: Any) -> str:
        """Preview the template with optional variables.

        Missing variables are shown as placeholders.

        Args:
            **variables: Optional variable values

        Returns:
            Preview of the rendered template
        """
        # For preview, apply defaults but let the renderer show placeholders
        # for variables that are still missing
        merged_vars = dict(variables)
        # Apply defaults from config
        for var in self.config.variables:
            if var.name not in merged_vars and var.default is not None:
                merged_vars[var.name] = var.default
        return self._renderer.preview(self.config.template, merged_vars)

    def get_required_variables(self) -> list[str]:
        """Get names of required variables without defaults.

        Returns:
            List of required variable names
        """
        return [
            v.name
            for v in self.config.variables
            if v.required and v.default is None
        ]

    def get_all_variables(self) -> set[str]:
        """Get all variable names used in the template.

        Returns:
            Set of variable names
        """
        return self._renderer.extract_variables(self.config.template)

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary representation.

        Returns:
            Dictionary representation of the template
        """
        return self.config.model_dump(by_alias=True, exclude_none=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"Template(name='{self.name}', variables={len(self.variables)})"
