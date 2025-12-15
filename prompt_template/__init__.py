"""Prompt Template - A tool for managing and rendering LLM prompts."""

# Analysis imports
from .analyzer import TemplateAnalyzer, TokenCounter
from .models import (
    AnalysisResult,
    ModelConfig,
    StructuralAnalysis,
    TemplateConfig,
    TokenEstimate,
    VariableAnalysis,
    VariableConfig,
    VariableType,
)

# Quality scoring imports
from .quality import DimensionScore, QualityDimension, QualityReport, QualityScorer
from .registry import TemplateInfo, TemplateRegistry
from .renderer import TemplateRenderer

# Semantic validation imports
from .semantic import SemanticIssue, SemanticValidationResult, SemanticValidator
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
    # Analysis models
    "TokenEstimate",
    "VariableAnalysis",
    "StructuralAnalysis",
    "AnalysisResult",
    # Exceptions
    "TemplateError",
    "TemplateNotFoundError",
    "TemplateValidationError",
    "TemplateRenderError",
    # Analysis
    "TemplateAnalyzer",
    "TokenCounter",
    # Semantic validation
    "SemanticValidator",
    "SemanticValidationResult",
    "SemanticIssue",
    # Quality scoring
    "QualityScorer",
    "QualityReport",
    "QualityDimension",
    "DimensionScore",
]
