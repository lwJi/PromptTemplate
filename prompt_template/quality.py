"""Quality metrics for prompt templates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from .analyzer import TokenCounter

if TYPE_CHECKING:
    from .models import TemplateConfig


class QualityDimension(str, Enum):
    """Quality dimensions for scoring."""

    CLARITY = "clarity"
    CONSISTENCY = "consistency"
    COMPLETENESS = "completeness"
    EFFICIENCY = "efficiency"
    STRUCTURE = "structure"


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""

    dimension: QualityDimension
    score: int  # 0-100
    weight: float  # Weight in overall calculation
    details: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """Complete quality assessment report."""

    template_name: str
    overall_score: int  # 0-100
    grade: str  # A, B, C, D, F
    dimensions: dict[QualityDimension, DimensionScore] = field(default_factory=dict)
    summary: str = ""
    top_suggestions: list[str] = field(default_factory=list)

    @property
    def is_production_ready(self) -> bool:
        """Check if template meets production quality threshold."""
        return self.overall_score >= 70

    def format_report(self) -> str:
        """Format as human-readable report."""
        lines = [
            f"Quality Report: {self.template_name}",
            "=" * 50,
            f"Overall Score: {self.overall_score}/100 (Grade: {self.grade})",
            "",
            "Dimension Scores:",
        ]

        for dim, score in self.dimensions.items():
            lines.append(f"  {dim.value.title()}: {score.score}/100")
            for detail in score.details[:2]:  # Top 2 details
                lines.append(f"    - {detail}")

        if self.top_suggestions:
            lines.append("")
            lines.append("Top Suggestions:")
            for i, suggestion in enumerate(self.top_suggestions[:5], 1):
                lines.append(f"  {i}. {suggestion}")

        return "\n".join(lines)


class QualityScorer:
    """Calculates quality metrics for prompt templates."""

    # Dimension weights (must sum to 1.0)
    DIMENSION_WEIGHTS: ClassVar[dict[QualityDimension, float]] = {
        QualityDimension.CLARITY: 0.25,
        QualityDimension.CONSISTENCY: 0.20,
        QualityDimension.COMPLETENESS: 0.25,
        QualityDimension.EFFICIENCY: 0.15,
        QualityDimension.STRUCTURE: 0.15,
    }

    # Grade thresholds
    GRADE_THRESHOLDS: ClassVar[list[tuple[int, str]]] = [
        (90, "A"),
        (80, "B"),
        (70, "C"),
        (60, "D"),
        (0, "F"),
    ]

    def __init__(self) -> None:
        """Initialize the quality scorer."""
        self.token_counter = TokenCounter()

    def score(
        self,
        config: TemplateConfig,
        sample_values: dict[str, Any] | None = None,
    ) -> QualityReport:
        """Calculate quality score for a template.

        Args:
            config: Template configuration
            sample_values: Optional sample values for analysis

        Returns:
            QualityReport with scores and suggestions
        """
        # Calculate individual dimension scores
        dimensions: dict[QualityDimension, DimensionScore] = {}

        dimensions[QualityDimension.CLARITY] = self._score_clarity(config)
        dimensions[QualityDimension.CONSISTENCY] = self._score_consistency(config)
        dimensions[QualityDimension.COMPLETENESS] = self._score_completeness(config)
        dimensions[QualityDimension.EFFICIENCY] = self._score_efficiency(
            config, sample_values
        )
        dimensions[QualityDimension.STRUCTURE] = self._score_structure(config)

        # Calculate weighted overall score
        overall_score = sum(
            score.score * score.weight for score in dimensions.values()
        )
        overall_score = int(overall_score)

        # Determine grade
        grade = "F"
        for threshold, g in self.GRADE_THRESHOLDS:
            if overall_score >= threshold:
                grade = g
                break

        # Collect top suggestions
        all_suggestions: list[str] = []
        for dim_score in dimensions.values():
            all_suggestions.extend(dim_score.suggestions)

        # Deduplicate and prioritize
        top_suggestions = list(dict.fromkeys(all_suggestions))[:5]

        # Generate summary
        summary = self._generate_summary(overall_score, grade)

        return QualityReport(
            template_name=config.name,
            overall_score=overall_score,
            grade=grade,
            dimensions=dimensions,
            summary=summary,
            top_suggestions=top_suggestions,
        )

    def _score_clarity(self, config: TemplateConfig) -> DimensionScore:
        """Score clarity of the template."""
        score = 100
        details: list[str] = []
        suggestions: list[str] = []

        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )

        # Check for clear role definition
        role_patterns = [r"you are", r"act as", r"<role>", r"<persona>"]
        has_role = any(
            re.search(p, all_content, re.IGNORECASE) for p in role_patterns
        )
        if has_role:
            details.append("Clear role definition found")
        else:
            score -= 15
            details.append("No clear role definition")
            suggestions.append("Add a clear role definition (e.g., 'You are a...')")

        # Check for clear task/instructions
        task_patterns = [
            r"your (task|goal|job) is",
            r"please",
            r"<task>",
            r"<instructions>",
        ]
        has_task = any(
            re.search(p, all_content, re.IGNORECASE) for p in task_patterns
        )
        if has_task:
            details.append("Clear task instructions present")
        else:
            score -= 15
            details.append("Task instructions could be clearer")
            suggestions.append("Add explicit task instructions")

        # Check for output format specification
        output_patterns = [r"<output_format>", r"respond in", r"format your"]
        has_output = any(
            re.search(p, all_content, re.IGNORECASE) for p in output_patterns
        )
        if has_output:
            details.append("Output format specified")
        else:
            score -= 10
            details.append("No output format specification")
            suggestions.append("Specify expected output format")

        # Check variable descriptions
        vars_with_desc = sum(1 for v in config.variables if v.description)
        total_vars = len(config.variables)
        if total_vars > 0:
            desc_ratio = vars_with_desc / total_vars
            if desc_ratio < 0.5:
                score -= 10
                details.append(
                    f"Only {vars_with_desc}/{total_vars} variables have descriptions"
                )
                suggestions.append("Add descriptions to all variables")
            else:
                details.append(f"{vars_with_desc}/{total_vars} variables documented")

        # Check for ambiguous language
        ambiguous_patterns = [
            r"\bmaybe\b",
            r"\bperhaps\b",
            r"\bmight want to\b",
            r"\bcould potentially\b",
        ]
        ambiguous_count = sum(
            len(re.findall(p, all_content, re.IGNORECASE))
            for p in ambiguous_patterns
        )
        if ambiguous_count > 2:
            score -= 10
            details.append(f"Found {ambiguous_count} ambiguous phrases")
            suggestions.append("Replace ambiguous language with direct instructions")

        return DimensionScore(
            dimension=QualityDimension.CLARITY,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.CLARITY],
            details=details,
            suggestions=suggestions,
        )

    def _score_consistency(self, config: TemplateConfig) -> DimensionScore:
        """Score consistency of the template."""
        score = 100
        details: list[str] = []
        suggestions: list[str] = []

        # Check naming consistency
        var_names = [v.name for v in config.variables]

        # Check for mixed naming conventions
        snake_case = sum(1 for n in var_names if "_" in n)
        camel_case = sum(1 for n in var_names if re.search(r"[a-z][A-Z]", n))

        if snake_case > 0 and camel_case > 0:
            score -= 15
            details.append("Mixed naming conventions (snake_case and camelCase)")
            suggestions.append("Use consistent naming convention for variables")
        elif var_names:
            details.append("Consistent variable naming")

        # Check type consistency
        for var in config.variables:
            if var.type.value == "string" and var.enum:
                if any(not isinstance(e, str) for e in var.enum):
                    score -= 10
                    details.append(
                        f"Variable '{var.name}' has inconsistent enum types"
                    )

        # Check for consistent structure across prompts
        if config.system_prompt and config.user_prompt:
            # Check if both use similar formatting (XML tags, markdown, etc.)
            sys_has_xml = "<" in config.system_prompt and ">" in config.system_prompt
            user_has_xml = "<" in config.user_prompt and ">" in config.user_prompt

            if sys_has_xml != user_has_xml:
                score -= 10
                details.append(
                    "Inconsistent formatting between system_prompt and user_prompt"
                )
                suggestions.append(
                    "Use consistent formatting (XML tags, markdown) throughout"
                )
            else:
                details.append("Consistent formatting across prompts")

        # Check for duplicate content
        if config.system_prompt and config.user_prompt:
            sys_sentences = {
                s.strip().lower()
                for s in config.system_prompt.split(".")
                if len(s.strip()) > 30
            }
            user_sentences = {
                s.strip().lower()
                for s in config.user_prompt.split(".")
                if len(s.strip()) > 30
            }

            overlap = sys_sentences & user_sentences
            if overlap:
                score -= 10
                details.append("Duplicate content found between prompts")
                suggestions.append(
                    "Remove duplicate content between system_prompt and user_prompt"
                )

        return DimensionScore(
            dimension=QualityDimension.CONSISTENCY,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.CONSISTENCY],
            details=details,
            suggestions=suggestions,
        )

    def _score_completeness(self, config: TemplateConfig) -> DimensionScore:
        """Score completeness of the template."""
        score = 100
        details: list[str] = []
        suggestions: list[str] = []

        # Check metadata completeness
        if not config.description:
            score -= 10
            details.append("Missing description")
            suggestions.append("Add a template description")
        else:
            if len(config.description) < 20:
                score -= 5
                details.append("Description is very brief")
                suggestions.append("Expand the template description")
            else:
                details.append("Description present")

        if not config.tags:
            score -= 5
            details.append("No tags defined")
            suggestions.append("Add tags for better discoverability")
        else:
            details.append(f"{len(config.tags)} tags defined")

        # Check variable completeness
        missing_desc_vars: list[str] = []
        for var in config.variables:
            if not var.description:
                missing_desc_vars.append(var.name)

            # Check for enums on constrained variables
            constrained_names = ["style", "format", "type", "mode", "level"]
            if var.name in constrained_names and not var.enum:
                score -= 5
                suggestions.append(f"Consider adding enum values for '{var.name}'")

        if missing_desc_vars:
            score -= min(15, len(missing_desc_vars) * 3)
            details.append(
                f"Variables without descriptions: {', '.join(missing_desc_vars[:3])}"
                + ("..." if len(missing_desc_vars) > 3 else "")
            )
            suggestions.append("Add descriptions to all variables")

        # Check for default values
        vars_with_defaults = sum(
            1 for v in config.variables if v.default is not None
        )
        optional_vars = sum(1 for v in config.variables if not v.required)
        if optional_vars > 0 and vars_with_defaults == 0:
            score -= 5
            details.append("Optional variables have no default values")
            suggestions.append("Add default values for optional variables")

        # Check for required components
        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )

        # Should have some kind of structure for longer templates
        has_structure = any(
            [
                "<" in all_content and ">" in all_content,  # XML tags
                "##" in all_content or "===" in all_content,  # Sections
            ]
        )

        if len(all_content) > 500 and not has_structure:
            score -= 10
            details.append("Long template without clear structure")
            suggestions.append(
                "Add sections or XML tags to organize longer templates"
            )

        return DimensionScore(
            dimension=QualityDimension.COMPLETENESS,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.COMPLETENESS],
            details=details,
            suggestions=suggestions,
        )

    def _score_efficiency(
        self,
        config: TemplateConfig,
        sample_values: dict[str, Any] | None = None,
    ) -> DimensionScore:
        """Score efficiency of the template."""
        score = 100
        details: list[str] = []
        suggestions: list[str] = []

        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )

        # Check token efficiency
        token_count = self.token_counter.count_tokens(all_content)

        if token_count > 10000:
            score -= 30
            details.append(f"Very high token count: {token_count}")
            suggestions.append("Consider breaking into smaller templates")
        elif token_count > 5000:
            score -= 15
            details.append(f"High token count: {token_count}")
            suggestions.append("Review for unnecessary content")
        else:
            details.append(f"Token count: {token_count}")

        # Check for redundancy (repeated words)
        words = all_content.lower().split()
        word_freq: dict[str, int] = {}
        for word in words:
            if len(word) > 4:
                word_freq[word] = word_freq.get(word, 0) + 1

        high_freq_words = [(w, c) for w, c in word_freq.items() if c > 5]
        if high_freq_words:
            top_repeated = sorted(high_freq_words, key=lambda x: -x[1])[:3]
            details.append(
                f"Frequently repeated words: {', '.join(w for w, _ in top_repeated)}"
            )
            if any(c > 10 for _, c in high_freq_words):
                score -= 10
                suggestions.append("Review template for unnecessary repetition")

        # Check variable usage efficiency
        for var in config.variables:
            pattern = r"\{\{\s*" + re.escape(var.name) + r"\s*\}\}"
            usage_count = len(re.findall(pattern, all_content))
            if usage_count > 5:
                score -= 5
                details.append(f"Variable '{var.name}' used {usage_count} times")
                suggestions.append(
                    f"Consider if '{var.name}' needs to be repeated {usage_count} times"
                )

        # Check for overly complex Jinja logic
        jinja_blocks = len(re.findall(r"\{%", all_content))
        if jinja_blocks > 10:
            score -= 15
            details.append(f"High Jinja complexity: {jinja_blocks} blocks")
            suggestions.append(
                "Simplify template logic or split into multiple templates"
            )

        return DimensionScore(
            dimension=QualityDimension.EFFICIENCY,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.EFFICIENCY],
            details=details,
            suggestions=suggestions,
        )

    def _score_structure(self, config: TemplateConfig) -> DimensionScore:
        """Score structural quality of the template."""
        score = 100
        details: list[str] = []
        suggestions: list[str] = []

        # Check for proper system/user split
        if config.system_prompt or config.user_prompt:
            if config.system_prompt and config.user_prompt:
                score += 5  # Bonus for proper structure
                details.append("Uses system_prompt/user_prompt split")
            elif config.system_prompt and not config.user_prompt:
                score -= 10
                details.append("Has system_prompt but no user_prompt")
                suggestions.append("Add user_prompt for complete chat structure")
        else:
            if config.template:
                details.append("Uses single template format")
                # Check if it would benefit from split
                if len(config.template) > 2000:
                    msg = "Consider using system_prompt/user_prompt split"
                    suggestions.append(msg)

        # Check section organization
        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )

        # Count structural elements
        xml_tags = len(re.findall(r"<[a-z_]+>", all_content, re.IGNORECASE))
        md_headers = len(re.findall(r"^#{1,3}\s", all_content, re.MULTILINE))
        section_markers = len(re.findall(r"^===", all_content, re.MULTILINE))

        total_structure = xml_tags + md_headers + section_markers

        if len(all_content) > 1000:
            if total_structure < 3:
                score -= 15
                details.append("Long template with minimal structure")
                suggestions.append(
                    "Add XML tags or section headers to organize content"
                )
            else:
                details.append(f"Good structure: {total_structure} structural elements")

        # Check nesting depth
        max_depth = 0
        current_depth = 0
        for match in re.finditer(
            r"\{%\s*(if|for|endif|endfor)\s*", all_content
        ):
            tag = match.group(1)
            if tag in ("if", "for"):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            else:
                current_depth = max(0, current_depth - 1)

        if max_depth > 3:
            score -= 15
            details.append(f"Deep nesting: {max_depth} levels")
            suggestions.append("Reduce nesting depth for better readability")
        elif max_depth > 0:
            details.append(f"Nesting depth: {max_depth}")

        return DimensionScore(
            dimension=QualityDimension.STRUCTURE,
            score=min(100, max(0, score)),  # Clamp to 0-100
            weight=self.DIMENSION_WEIGHTS[QualityDimension.STRUCTURE],
            details=details,
            suggestions=suggestions,
        )

    def _generate_summary(self, overall_score: int, grade: str) -> str:
        """Generate a summary of the quality assessment."""
        if grade == "A":
            return "Excellent quality template, ready for production use."
        elif grade == "B":
            return "Good quality template with minor improvements possible."
        elif grade == "C":
            return "Acceptable template, but several areas need attention."
        elif grade == "D":
            return "Below average quality, significant improvements recommended."
        else:
            return "Poor quality template, requires substantial revision."
