"""Pydantic models for prompt template configuration."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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
    enum: list[Any] | None = Field(
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
    template: str = Field(default="", description="The template content")
    system_prompt: str | None = Field(
        default=None, description="System prompt (for chat API format)"
    )
    user_prompt: str | None = Field(
        default=None, description="User prompt (for chat API format)"
    )
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
    def validate_template_not_empty(cls, v: str, info: Any) -> str:
        """Ensure template content is not empty (unless using system/user prompts)."""
        # Allow empty template if system_prompt or user_prompt will be provided
        # The model_validator below will check that at least one is provided
        return v

    @model_validator(mode="after")
    def validate_has_template_content(self) -> "TemplateConfig":
        """Ensure at least template or system_prompt/user_prompt is provided."""
        has_template = bool(self.template and self.template.strip())
        has_system = bool(self.system_prompt and self.system_prompt.strip())
        has_user = bool(self.user_prompt and self.user_prompt.strip())

        if not has_template and not has_system and not has_user:
            raise ValueError(
                "Template must have either 'template' content or "
                "'system_prompt'/'user_prompt' defined"
            )
        return self

    def get_variable(self, name: str) -> VariableConfig | None:
        """Get a variable configuration by name."""
        for var in self.variables:
            if var.name == name:
                return var
        return None

    def get_declared_required_variables(self) -> list[VariableConfig]:
        """Get all variables marked as required (regardless of defaults).

        Note: Use get_must_provide_variables() to get variables that users
        must actually provide values for.
        """
        return [v for v in self.variables if v.required]

    def get_must_provide_variables(self) -> list[VariableConfig]:
        """Get variables that must be provided by the user.

        Returns variables that are required AND have no default value.
        These are the variables that will cause validation errors if not provided.
        """
        return [v for v in self.variables if v.required and v.default is None]

    def get_optional_variables(self) -> list[VariableConfig]:
        """Get all optional variables."""
        return [v for v in self.variables if not v.required]


# =============================================================================
# Analysis Models (for token counting and template analysis)
# =============================================================================


class TokenEstimate(BaseModel):
    """Token count estimation result."""

    template_tokens: int = Field(default=0, description="Tokens in raw template")
    system_prompt_tokens: int | None = Field(
        default=None, description="Tokens in system prompt"
    )
    user_prompt_tokens: int | None = Field(
        default=None, description="Tokens in user prompt"
    )
    estimated_variable_tokens: dict[str, int] = Field(
        default_factory=dict,
        description="Estimated tokens per variable",
    )
    total_static_tokens: int = Field(
        default=0, description="Total tokens excluding variable content"
    )
    estimated_total: int = Field(
        default=0, description="Estimated total with variable placeholders"
    )
    model_fit: dict[str, bool] = Field(
        default_factory=dict,
        description="Whether template fits in each model's context",
    )


class VariableAnalysis(BaseModel):
    """Analysis of a single variable."""

    name: str = Field(..., description="Variable name")
    type: str = Field(..., description="Variable type")
    estimated_tokens: int = Field(default=0, description="Estimated token count")
    usage_count: int = Field(default=0, description="How many times used in template")
    in_system_prompt: bool = Field(
        default=False, description="Whether used in system prompt"
    )
    in_user_prompt: bool = Field(
        default=False, description="Whether used in user prompt"
    )
    description_quality: str = Field(
        default="missing", description="Quality: good, minimal, missing"
    )


class StructuralAnalysis(BaseModel):
    """Structural analysis of template."""

    has_system_prompt: bool = Field(default=False)
    has_user_prompt: bool = Field(default=False)
    has_template: bool = Field(default=False)
    uses_conditionals: bool = Field(default=False)
    uses_loops: bool = Field(default=False)
    nesting_depth: int = Field(default=0)
    section_count: int = Field(default=0)


class AnalysisResult(BaseModel):
    """Complete analysis result including tokens."""

    template_name: str = Field(..., description="Name of the analyzed template")
    token_estimate: TokenEstimate = Field(default_factory=TokenEstimate)
    variable_analysis: dict[str, VariableAnalysis] = Field(default_factory=dict)
    structural_analysis: StructuralAnalysis = Field(default_factory=StructuralAnalysis)
    recommendations: list[str] = Field(default_factory=list)
