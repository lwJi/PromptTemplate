"""Template validation utilities."""

from dataclasses import dataclass, field
from typing import Any

from .models import TemplateConfig, VariableType
from .renderer import TemplateRenderer


@dataclass
class ValidationResult:
    """Result of template validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False


class TemplateValidator:
    """Validates template configuration and content."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self.renderer = TemplateRenderer()

    def validate(self, config: TemplateConfig) -> ValidationResult:
        """Perform full validation on a template configuration.

        Args:
            config: The template configuration to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(is_valid=True)

        # Validate syntax
        syntax_result = self.validate_syntax(config.template)
        result.merge(syntax_result)

        # Validate variables
        var_result = self.validate_variables(config)
        result.merge(var_result)

        # Check for unused variables
        unused_result = self.check_unused_variables(config)
        result.merge(unused_result)

        # Check for undeclared variables
        undeclared_result = self.check_undeclared_variables(config)
        result.merge(undeclared_result)

        return result

    def validate_syntax(self, template_string: str) -> ValidationResult:
        """Validate template syntax.

        Args:
            template_string: The template string to validate

        Returns:
            ValidationResult with syntax errors
        """
        result = ValidationResult(is_valid=True)

        errors = self.renderer.validate_syntax(template_string)
        for error in errors:
            result.add_error(error)

        return result

    def validate_variables(self, config: TemplateConfig) -> ValidationResult:
        """Validate variable configurations.

        Args:
            config: The template configuration

        Returns:
            ValidationResult with variable errors
        """
        result = ValidationResult(is_valid=True)

        seen_names: set[str] = set()
        for var in config.variables:
            # Check for duplicate variable names
            if var.name in seen_names:
                result.add_error(f"Duplicate variable name: '{var.name}'")
            seen_names.add(var.name)

            # Validate default value matches type
            if var.default is not None:
                type_result = self._validate_value_type(
                    var.name, var.default, var.type
                )
                result.merge(type_result)

            # Validate default value is in enum if specified
            if var.enum and var.default is not None:
                if var.default not in var.enum:
                    result.add_error(
                        f"Default value '{var.default}' for variable '{var.name}' "
                        f"is not in enum: {var.enum}"
                    )

        return result

    def _validate_value_type(
        self, name: str, value: Any, expected_type: VariableType
    ) -> ValidationResult:
        """Validate a value matches the expected type.

        Args:
            name: Variable name (for error messages)
            value: The value to validate
            expected_type: Expected variable type

        Returns:
            ValidationResult with type errors
        """
        result = ValidationResult(is_valid=True)

        def is_int(v: Any) -> bool:
            return isinstance(v, int) and not isinstance(v, bool)

        def is_float(v: Any) -> bool:
            return isinstance(v, (int, float)) and not isinstance(v, bool)

        type_checks = {
            VariableType.STRING: lambda v: isinstance(v, str),
            VariableType.INTEGER: is_int,
            VariableType.FLOAT: is_float,
            VariableType.BOOLEAN: lambda v: isinstance(v, bool),
            VariableType.LIST: lambda v: isinstance(v, list),
            VariableType.OBJECT: lambda v: isinstance(v, dict),
        }

        check_fn = type_checks.get(expected_type)
        if check_fn and not check_fn(value):
            result.add_error(
                f"Variable '{name}' has value of type {type(value).__name__}, "
                f"expected {expected_type.value}"
            )

        return result

    def check_unused_variables(self, config: TemplateConfig) -> ValidationResult:
        """Check for variables defined but not used in template.

        Args:
            config: The template configuration

        Returns:
            ValidationResult with warnings for unused variables
        """
        result = ValidationResult(is_valid=True)

        template_vars = self.renderer.extract_variables(config.template)
        defined_vars = {v.name for v in config.variables}

        unused = defined_vars - template_vars
        for var_name in unused:
            result.add_warning(
                f"Variable '{var_name}' is defined but not used in template"
            )

        return result

    def check_undeclared_variables(self, config: TemplateConfig) -> ValidationResult:
        """Check for variables used in template but not defined.

        Args:
            config: The template configuration

        Returns:
            ValidationResult with errors for undeclared variables
        """
        result = ValidationResult(is_valid=True)

        template_vars = self.renderer.extract_variables(config.template)
        defined_vars = {v.name for v in config.variables}

        undeclared = template_vars - defined_vars
        for var_name in undeclared:
            result.add_warning(
                f"Variable '{var_name}' is used in template but not declared"
            )

        return result

    def validate_inputs(
        self, config: TemplateConfig, inputs: dict[str, Any]
    ) -> ValidationResult:
        """Validate input values against template configuration.

        Args:
            config: The template configuration
            inputs: Dictionary of input values

        Returns:
            ValidationResult with input validation errors
        """
        result = ValidationResult(is_valid=True)

        # Check required variables are provided
        for var in config.get_required_variables():
            if var.name not in inputs and var.default is None:
                result.add_error(f"Missing required variable: '{var.name}'")

        # Validate provided values
        for name, value in inputs.items():
            var_config = config.get_variable(name)
            if var_config is None:
                result.add_warning(f"Unknown variable provided: '{name}'")
                continue

            # Type validation
            type_result = self._validate_value_type(name, value, var_config.type)
            result.merge(type_result)

            # Enum validation
            if var_config.enum is not None and value not in var_config.enum:
                result.add_error(
                    f"Value '{value}' for variable '{name}' is not in "
                    f"allowed values: {var_config.enum}"
                )

        return result
