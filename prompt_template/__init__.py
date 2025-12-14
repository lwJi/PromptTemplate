"""Prompt Template - A tool for managing and rendering LLM prompts."""

from .models import ModelConfig, TemplateConfig, VariableConfig, VariableType
from .registry import TemplateInfo, TemplateRegistry
from .renderer import TemplateRenderer
from .template import (
    Template,
    TemplateError,
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateValidationError,
)
from .validator import TemplateValidator, ValidationResult

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "Template",
    "TemplateRegistry",
    "TemplateRenderer",
    "TemplateValidator",
    # Models
    "TemplateConfig",
    "VariableConfig",
    "VariableType",
    "ModelConfig",
    "TemplateInfo",
    "ValidationResult",
    # Exceptions
    "TemplateError",
    "TemplateNotFoundError",
    "TemplateValidationError",
    "TemplateRenderError",
]
