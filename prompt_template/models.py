"""Pydantic models for prompt template configuration."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class VariableType(str, Enum):
    """Supported variable types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    OBJECT = "object"


class VariableConfig(BaseModel):
    """Configuration for a template variable."""

    name: str = Field(..., description="Variable name")
    type: VariableType = Field(
        default=VariableType.STRING, description="Variable type"
    )
    required: bool = Field(default=True, description="Whether variable is required")
    default: Any = Field(default=None, description="Default value if not provided")
    description: str = Field(default="", description="Variable description")
    enum: list[str] | None = Field(
        default=None, description="Allowed values for the variable"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate variable name is a valid identifier."""
        if not v.isidentifier():
            raise ValueError(
                f"Variable name '{v}' must be a valid Python identifier "
                "(letters, digits, underscores, not starting with a digit)"
            )
        return v

    @field_validator("default")
    @classmethod
    def validate_default_with_required(cls, v: Any, info: Any) -> Any:
        """Ensure required variables don't have defaults (unless explicitly set)."""
        # Allow defaults even for required variables - they serve as fallbacks
        return v


class ModelConfig(BaseModel):
    """Configuration for LLM model settings."""

    model: str = Field(default="", description="Model identifier")
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: int | None = Field(
        default=None, ge=1, description="Maximum tokens in response"
    )
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-p sampling")


class TemplateConfig(BaseModel):
    """Complete template configuration."""

    name: str = Field(..., description="Template name")
    description: str = Field(default="", description="Template description")
    version: str = Field(default="1.0.0", description="Template version")
    author: str = Field(default="", description="Template author")
    tags: list[str] = Field(default_factory=list, description="Template tags")
    variables: list[VariableConfig] = Field(
        default_factory=list, description="Template variables"
    )
    template: str = Field(..., description="The template content")
    model_config_settings: ModelConfig | None = Field(
        default=None,
        alias="model_config",
        description="Optional model configuration",
    )

    model_config = {"populate_by_name": True}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate template name."""
        if not v.strip():
            raise ValueError("Template name cannot be empty")
        # Allow alphanumeric, hyphens, underscores
        clean_name = v.replace("-", "").replace("_", "")
        if not clean_name.replace(" ", "").isalnum():
            raise ValueError(
                f"Template name '{v}' should only contain letters, numbers, "
                "hyphens, underscores, and spaces"
            )
        return v

    @field_validator("template")
    @classmethod
    def validate_template_not_empty(cls, v: str) -> str:
        """Ensure template content is not empty."""
        if not v.strip():
            raise ValueError("Template content cannot be empty")
        return v

    def get_variable(self, name: str) -> VariableConfig | None:
        """Get a variable configuration by name."""
        for var in self.variables:
            if var.name == name:
                return var
        return None

    def get_required_variables(self) -> list[VariableConfig]:
        """Get all required variables."""
        return [v for v in self.variables if v.required]

    def get_optional_variables(self) -> list[VariableConfig]:
        """Get all optional variables."""
        return [v for v in self.variables if not v.required]
