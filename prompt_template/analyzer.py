"""Template analysis and token counting utilities."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

from .models import (
    AnalysisResult,
    StructuralAnalysis,
    TokenEstimate,
    VariableAnalysis,
)

if TYPE_CHECKING:
    from .models import TemplateConfig, VariableConfig


# Model context window limits (in tokens)
MODEL_LIMITS: dict[str, int] = {
    # OpenAI models
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-3.5-turbo": 16385,
    # Anthropic models
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3.5-sonnet": 200000,
    "claude-2": 100000,
    # Default fallback
    "default": 8192,
}


def get_model_limit(model: str) -> int:
    """Get token limit for a model name.

    Args:
        model: Model name or identifier

    Returns:
        Token limit for the model
    """
    model_lower = model.lower()

    # Exact match
    if model_lower in MODEL_LIMITS:
        return MODEL_LIMITS[model_lower]

    # Fuzzy matching
    for key, limit in MODEL_LIMITS.items():
        if key in model_lower or model_lower in key:
            return limit

    return MODEL_LIMITS["default"]


class TokenCounter:
    """Estimates token counts for templates."""

    # Average chars per token (conservative estimate)
    DEFAULT_CHARS_PER_TOKEN: ClassVar[float] = 4.0

    # Class-level cache for tiktoken
    _encoding: ClassVar[Any] = None
    _tiktoken_available: ClassVar[bool | None] = None

    def __init__(self, use_tiktoken: bool = True) -> None:
        """Initialize token counter.

        Args:
            use_tiktoken: Whether to use tiktoken if available
        """
        self._use_tiktoken = use_tiktoken
        if use_tiktoken:
            self._check_tiktoken()

    @classmethod
    def _check_tiktoken(cls) -> bool:
        """Check if tiktoken is available and initialize encoding."""
        if cls._tiktoken_available is None:
            try:
                import tiktoken

                cls._encoding = tiktoken.get_encoding("cl100k_base")
                cls._tiktoken_available = True
            except ImportError:
                cls._tiktoken_available = False
        return cls._tiktoken_available

    @property
    def tiktoken_available(self) -> bool:
        """Check if tiktoken is available."""
        return bool(self._tiktoken_available)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Uses tiktoken if available, falls back to character estimation.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        if not text:
            return 0

        if self._use_tiktoken and self._tiktoken_available and self._encoding:
            return len(self._encoding.encode(text))

        # Fallback: character-based estimation
        return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate tokens using character count heuristic.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Basic estimation: chars / 4
        base_estimate = len(text) / self.DEFAULT_CHARS_PER_TOKEN

        # Adjust for whitespace (each significant whitespace is ~1 token)
        whitespace_count = len(re.findall(r"\s+", text))

        return int(base_estimate + whitespace_count * 0.25)

    def estimate_variable_tokens(
        self,
        var_config: VariableConfig,
        sample_values: dict[str, Any] | None = None,
    ) -> int:
        """Estimate tokens a variable might contribute.

        Args:
            var_config: Variable configuration
            sample_values: Optional sample values for estimation

        Returns:
            Estimated token count
        """
        # Use sample if provided
        if sample_values and var_config.name in sample_values:
            value = sample_values[var_config.name]
            return self.count_tokens(str(value))

        # Use default if available
        if var_config.default is not None:
            return self.count_tokens(str(var_config.default))

        # Estimate based on type and description
        type_estimates: dict[str, int] = {
            "string": 50,
            "integer": 2,
            "float": 3,
            "boolean": 1,
            "list": 100,
            "object": 150,
        }

        base = type_estimates.get(var_config.type.value, 50)

        # Adjust if description hints at size
        if var_config.description:
            desc_lower = var_config.description.lower()
            if any(
                word in desc_lower
                for word in ["long", "large", "full", "complete", "code", "content"]
            ):
                base *= 5
            elif any(word in desc_lower for word in ["short", "brief", "single"]):
                base //= 2

        return base


class TemplateAnalyzer:
    """Analyzes templates for tokens, structure, and recommendations."""

    def __init__(self) -> None:
        """Initialize the analyzer."""
        self.token_counter = TokenCounter()

    def analyze(
        self,
        config: TemplateConfig,
        sample_values: dict[str, Any] | None = None,
        target_models: list[str] | None = None,
    ) -> AnalysisResult:
        """Perform complete analysis on a template.

        Args:
            config: Template configuration
            sample_values: Optional sample variable values
            target_models: Models to check fit against

        Returns:
            Complete analysis result
        """
        token_estimate = self._estimate_tokens(config, sample_values)
        variable_analysis = self._analyze_variables(config, sample_values)
        structural_analysis = self._analyze_structure(config)

        # Check model fit
        models_to_check = target_models or ["gpt-4", "gpt-4-turbo", "claude-3-sonnet"]
        token_estimate.model_fit = self._check_model_fit(
            token_estimate.estimated_total, models_to_check
        )

        recommendations = self._generate_recommendations(
            config, token_estimate, variable_analysis, structural_analysis
        )

        return AnalysisResult(
            template_name=config.name,
            token_estimate=token_estimate,
            variable_analysis=variable_analysis,
            structural_analysis=structural_analysis,
            recommendations=recommendations,
        )

    def _estimate_tokens(
        self,
        config: TemplateConfig,
        sample_values: dict[str, Any] | None = None,
    ) -> TokenEstimate:
        """Estimate token counts for template.

        Args:
            config: Template configuration
            sample_values: Optional sample values

        Returns:
            Token estimate
        """
        system_tokens = None
        user_tokens = None
        template_tokens = 0

        if config.system_prompt:
            system_tokens = self.token_counter.count_tokens(config.system_prompt)
        if config.user_prompt:
            user_tokens = self.token_counter.count_tokens(config.user_prompt)
        if config.template:
            template_tokens = self.token_counter.count_tokens(config.template)

        # Variable token estimates
        var_tokens: dict[str, int] = {}
        for var in config.variables:
            var_tokens[var.name] = self.token_counter.estimate_variable_tokens(
                var, sample_values
            )

        total_static = (system_tokens or 0) + (user_tokens or 0) + template_tokens

        # Subtract variable placeholders (~2 tokens each), add variable estimates
        placeholder_tokens = len(config.variables) * 2
        estimated_total = (
            total_static - placeholder_tokens + sum(var_tokens.values())
        )

        return TokenEstimate(
            template_tokens=template_tokens,
            system_prompt_tokens=system_tokens,
            user_prompt_tokens=user_tokens,
            estimated_variable_tokens=var_tokens,
            total_static_tokens=total_static,
            estimated_total=max(0, estimated_total),
            model_fit={},
        )

    def _analyze_variables(
        self,
        config: TemplateConfig,
        sample_values: dict[str, Any] | None = None,
    ) -> dict[str, VariableAnalysis]:
        """Analyze each variable.

        Args:
            config: Template configuration
            sample_values: Optional sample values

        Returns:
            Dictionary of variable analyses
        """
        result: dict[str, VariableAnalysis] = {}

        # Get all content for analysis
        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )
        system_content = config.system_prompt or ""
        user_content = config.user_prompt or ""

        for var in config.variables:
            # Count usages (both {{ var }} and {{var}} patterns)
            usage_count = len(
                re.findall(r"\{\{\s*" + re.escape(var.name) + r"\s*\}\}", all_content)
            )

            # Check where variable is used
            in_system = bool(
                re.search(
                    r"\{\{\s*" + re.escape(var.name) + r"\s*\}\}", system_content
                )
            )
            in_user = bool(
                re.search(r"\{\{\s*" + re.escape(var.name) + r"\s*\}\}", user_content)
            )

            # Check description quality
            desc_quality = "missing"
            if var.description:
                if len(var.description) > 20:
                    desc_quality = "good"
                else:
                    desc_quality = "minimal"

            result[var.name] = VariableAnalysis(
                name=var.name,
                type=var.type.value,
                estimated_tokens=self.token_counter.estimate_variable_tokens(
                    var, sample_values
                ),
                usage_count=usage_count,
                in_system_prompt=in_system,
                in_user_prompt=in_user,
                description_quality=desc_quality,
            )

        return result

    def _analyze_structure(self, config: TemplateConfig) -> StructuralAnalysis:
        """Analyze template structure.

        Args:
            config: Template configuration

        Returns:
            Structural analysis
        """
        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )

        # Check for conditionals
        uses_conditionals = bool(
            re.search(r"\{%\s*(if|elif|else)\s*", all_content)
        )

        # Check for loops
        uses_loops = bool(re.search(r"\{%\s*for\s+", all_content))

        # Calculate nesting depth
        nesting_depth = self._calculate_nesting_depth(all_content)

        # Count sections (markdown headers, XML tags, or === markers)
        section_count = (
            len(re.findall(r"^#{1,3}\s", all_content, re.MULTILINE))
            + len(re.findall(r"<[a-z_]+>", all_content, re.IGNORECASE))
            + len(re.findall(r"^===", all_content, re.MULTILINE))
        )

        return StructuralAnalysis(
            has_system_prompt=bool(config.system_prompt),
            has_user_prompt=bool(config.user_prompt),
            has_template=bool(config.template),
            uses_conditionals=uses_conditionals,
            uses_loops=uses_loops,
            nesting_depth=nesting_depth,
            section_count=section_count,
        )

    def _calculate_nesting_depth(self, content: str) -> int:
        """Calculate maximum nesting depth of Jinja blocks.

        Args:
            content: Template content

        Returns:
            Maximum nesting depth
        """
        max_depth = 0
        current_depth = 0

        # Find all block starts and ends
        for match in re.finditer(
            r"\{%\s*(if|for|block|elif|else|endif|endfor|endblock)\s*", content
        ):
            tag = match.group(1)
            if tag in ("if", "for", "block"):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif tag in ("endif", "endfor", "endblock"):
                current_depth = max(0, current_depth - 1)

        return max_depth

    def _check_model_fit(
        self, tokens: int, models: list[str]
    ) -> dict[str, bool]:
        """Check if token count fits in model context windows.

        Args:
            tokens: Estimated token count
            models: List of model names

        Returns:
            Dictionary of model -> fits boolean
        """
        result: dict[str, bool] = {}
        for model in models:
            limit = get_model_limit(model)
            # Leave room for response (at least 25% of context)
            result[model] = tokens < (limit * 0.75)
        return result

    def _generate_recommendations(
        self,
        config: TemplateConfig,
        tokens: TokenEstimate,
        variables: dict[str, VariableAnalysis],
        structure: StructuralAnalysis,
    ) -> list[str]:
        """Generate recommendations based on analysis.

        Args:
            config: Template configuration
            tokens: Token estimate
            variables: Variable analyses
            structure: Structural analysis

        Returns:
            List of recommendations
        """
        recommendations: list[str] = []

        # Token-based recommendations
        if tokens.estimated_total > 10000:
            recommendations.append(
                "Consider breaking this template into smaller, focused templates "
                "for better token efficiency."
            )

        # Structure-based recommendations
        if not structure.has_system_prompt and not structure.has_user_prompt:
            if structure.section_count == 0 and tokens.total_static_tokens > 500:
                recommendations.append(
                    "Consider adding structure with system_prompt/user_prompt split "
                    "or markdown sections for better LLM comprehension."
                )

        if structure.nesting_depth > 3:
            recommendations.append(
                f"Template has deep nesting (depth: {structure.nesting_depth}). "
                "Consider simplifying conditional logic."
            )

        # Variable-based recommendations
        for var_name, var_analysis in variables.items():
            if var_analysis.description_quality == "missing":
                recommendations.append(
                    f"Variable '{var_name}' lacks a description. "
                    "Add one for better documentation."
                )
            if var_analysis.usage_count > 5:
                recommendations.append(
                    f"Variable '{var_name}' is used {var_analysis.usage_count} times. "
                    "Consider if this repetition is necessary."
                )

        # Description recommendation
        if not config.description:
            recommendations.append(
                "Template lacks a description. Add one for better discoverability."
            )

        return recommendations
