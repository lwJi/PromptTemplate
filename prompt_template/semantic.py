"""Semantic validation for prompt templates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from .validator import ValidationResult

if TYPE_CHECKING:
    from .models import TemplateConfig


class SemanticIssueType(str, Enum):
    """Types of semantic issues."""

    ROLE_CONFUSION = "role_confusion"
    INSTRUCTION_CLARITY = "instruction_clarity"
    CONTEXT_COHERENCE = "context_coherence"
    TASK_ALIGNMENT = "task_alignment"
    PLACEHOLDER_QUALITY = "placeholder_quality"
    PROMPT_STRUCTURE = "prompt_structure"


@dataclass
class SemanticIssue:
    """A semantic issue found in validation."""

    type: SemanticIssueType
    severity: str  # "error", "warning", "info"
    message: str
    location: str  # "system_prompt", "user_prompt", "template", "variables"
    suggestion: str | None = None


@dataclass
class SemanticValidationResult:
    """Result of semantic validation."""

    is_valid: bool = True
    issues: list[SemanticIssue] = field(default_factory=list)

    # Detailed scores (0-100)
    role_clarity_score: int = 100
    instruction_clarity_score: int = 100
    context_coherence_score: int = 100
    task_alignment_score: int = 100

    def add_issue(self, issue: SemanticIssue) -> None:
        """Add an issue to the result."""
        self.issues.append(issue)
        if issue.severity == "error":
            self.is_valid = False

    def to_validation_result(self) -> ValidationResult:
        """Convert to standard ValidationResult."""
        result = ValidationResult(is_valid=self.is_valid)
        for issue in self.issues:
            msg = f"[Semantic] {issue.message}"
            if issue.suggestion:
                msg += f" (Suggestion: {issue.suggestion})"

            if issue.severity == "error":
                result.add_error(msg)
            else:
                result.add_warning(msg)
        return result


class SemanticValidator:
    """Validates semantic coherence of prompt templates."""

    # Patterns indicating role definition
    ROLE_PATTERNS: ClassVar[list[str]] = [
        r"you are\s+(a|an|the)\s+",
        r"act as\s+(a|an|the)\s+",
        r"<role>",
        r"<persona>",
        r"your role is",
        r"you will be\s+(a|an|the)\s+",
        r"as\s+(a|an)\s+\w+,?\s+you",
    ]

    # Patterns indicating task/instruction
    TASK_PATTERNS: ClassVar[list[str]] = [
        r"your (task|job|goal|objective) is",
        r"you (should|must|will|need to)",
        r"please\s+\w+",
        r"<task>",
        r"<instructions>",
        r"i want you to",
        r"i need you to",
    ]

    # Patterns indicating output format specification
    OUTPUT_PATTERNS: ClassVar[list[str]] = [
        r"<output_format>",
        r"<output>",
        r"respond in (this|the following) format",
        r"format your (response|answer|output)",
        r"your (response|answer|output) should",
        r"use (this|the following) (format|structure)",
        r"return (the result|your answer) (as|in)",
    ]

    # Ambiguous language patterns
    AMBIGUOUS_PATTERNS: ClassVar[list[str]] = [
        r"\bmaybe\b",
        r"\bperhaps\b",
        r"\bmight want to\b",
        r"\bcould potentially\b",
        r"\bpossibly\b",
        r"\bif you want\b",
    ]

    def __init__(self) -> None:
        """Initialize the semantic validator."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns."""
        self._role_regex = [
            re.compile(p, re.IGNORECASE) for p in self.ROLE_PATTERNS
        ]
        self._task_regex = [
            re.compile(p, re.IGNORECASE) for p in self.TASK_PATTERNS
        ]
        self._output_regex = [
            re.compile(p, re.IGNORECASE) for p in self.OUTPUT_PATTERNS
        ]
        self._ambiguous_regex = [
            re.compile(p, re.IGNORECASE) for p in self.AMBIGUOUS_PATTERNS
        ]

    def validate(self, config: TemplateConfig) -> SemanticValidationResult:
        """Perform semantic validation on a template.

        Args:
            config: Template configuration to validate

        Returns:
            SemanticValidationResult with issues and scores
        """
        result = SemanticValidationResult()

        # Run all semantic checks
        self._check_role_definition(config, result)
        self._check_instruction_clarity(config, result)
        self._check_context_coherence(config, result)
        self._check_task_alignment(config, result)
        self._check_placeholder_quality(config, result)
        self._check_prompt_structure(config, result)

        return result

    def _check_role_definition(
        self, config: TemplateConfig, result: SemanticValidationResult
    ) -> None:
        """Check for clear role definition."""
        system_content = config.system_prompt or ""
        user_content = config.user_prompt or ""
        template_content = config.template or ""

        # Check system prompt for role
        has_role_in_system = any(
            p.search(system_content) for p in self._role_regex
        )

        # Check if role is in user prompt (wrong place)
        has_role_in_user = any(p.search(user_content) for p in self._role_regex)

        # For single template, check there
        has_role_in_template = any(
            p.search(template_content) for p in self._role_regex
        )

        has_role = has_role_in_system or has_role_in_template

        # Scoring
        if has_role:
            result.role_clarity_score = 100
        else:
            result.role_clarity_score = 60
            result.add_issue(
                SemanticIssue(
                    type=SemanticIssueType.ROLE_CONFUSION,
                    severity="info",
                    message="No clear role definition found in the prompt",
                    location="system_prompt" if config.system_prompt else "template",
                    suggestion="Add 'You are a [role]' to establish context",
                )
            )

        if has_role_in_user and config.system_prompt:
            result.role_clarity_score -= 20
            result.add_issue(
                SemanticIssue(
                    type=SemanticIssueType.ROLE_CONFUSION,
                    severity="warning",
                    message="Role definition found in user_prompt, not system_prompt",
                    location="user_prompt",
                    suggestion="Move role definition to system_prompt",
                )
            )

    def _check_instruction_clarity(
        self, config: TemplateConfig, result: SemanticValidationResult
    ) -> None:
        """Check for clear instructions."""
        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )

        # Check for task patterns
        has_task = any(p.search(all_content) for p in self._task_regex)

        # Check for output format
        has_output_format = any(p.search(all_content) for p in self._output_regex)

        # Check for ambiguous language
        ambiguous_count = sum(
            len(p.findall(all_content)) for p in self._ambiguous_regex
        )

        score = 100

        if not has_task:
            score -= 25
            result.add_issue(
                SemanticIssue(
                    type=SemanticIssueType.INSTRUCTION_CLARITY,
                    severity="info",
                    message="No clear task instructions found",
                    location="template",
                    suggestion="Add 'Your task is to...' or 'Please...'",
                )
            )

        if not has_output_format:
            score -= 15
            result.add_issue(
                SemanticIssue(
                    type=SemanticIssueType.INSTRUCTION_CLARITY,
                    severity="info",
                    message="No output format specification found",
                    location="user_prompt" if config.user_prompt else "template",
                    suggestion="Consider specifying expected output format",
                )
            )

        if ambiguous_count > 2:
            score -= 10
            result.add_issue(
                SemanticIssue(
                    type=SemanticIssueType.INSTRUCTION_CLARITY,
                    severity="info",
                    message=f"Found {ambiguous_count} ambiguous phrases",
                    location="template",
                    suggestion="Replace ambiguous language with direct instructions",
                )
            )

        result.instruction_clarity_score = max(0, score)

    def _check_context_coherence(
        self, config: TemplateConfig, result: SemanticValidationResult
    ) -> None:
        """Check for context coherence between parts."""
        score = 100

        if config.system_prompt and config.user_prompt:
            # Check for repeated content (potential redundancy)
            system_lower = config.system_prompt.lower()
            user_lower = config.user_prompt.lower()

            system_sentences = {
                s.strip()
                for s in system_lower.split(".")
                if len(s.strip()) > 30
            }
            user_sentences = {
                s.strip() for s in user_lower.split(".") if len(s.strip()) > 30
            }

            overlap = system_sentences & user_sentences
            if overlap:
                score -= 15
                result.add_issue(
                    SemanticIssue(
                        type=SemanticIssueType.CONTEXT_COHERENCE,
                        severity="info",
                        message="Content duplication between prompts",
                        location="user_prompt",
                        suggestion="Review and deduplicate repeated content",
                    )
                )

        result.context_coherence_score = max(0, score)

    def _check_task_alignment(
        self, config: TemplateConfig, result: SemanticValidationResult
    ) -> None:
        """Check if task description aligns with template structure."""
        score = 100

        desc_lower = config.description.lower() if config.description else ""
        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )
        content_lower = all_content.lower()

        if desc_lower:
            # Extract key terms from description (words 4+ chars)
            key_terms = set(re.findall(r"\b[a-z]{4,}\b", desc_lower))
            content_terms = set(re.findall(r"\b[a-z]{4,}\b", content_lower))

            # Check overlap
            if key_terms:
                overlap = key_terms & content_terms
                overlap_ratio = len(overlap) / len(key_terms)

                if overlap_ratio < 0.3:
                    score -= 20
                    result.add_issue(
                        SemanticIssue(
                            type=SemanticIssueType.TASK_ALIGNMENT,
                            severity="info",
                            message="Description may not align with template content",
                            location="description",
                            suggestion="Update description to reflect functionality",
                        )
                    )
        else:
            score -= 10
            result.add_issue(
                SemanticIssue(
                    type=SemanticIssueType.TASK_ALIGNMENT,
                    severity="info",
                    message="Template lacks a description",
                    location="description",
                    suggestion="Add a description to clarify the template's purpose",
                )
            )

        result.task_alignment_score = max(0, score)

    def _check_placeholder_quality(
        self, config: TemplateConfig, result: SemanticValidationResult
    ) -> None:
        """Check quality of variable placeholders."""
        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )

        # Find all variable usages
        var_usages = re.findall(r"\{\{\s*(\w+)\s*\}\}", all_content)

        for var_name in set(var_usages):
            # Check if variable exists in config
            var_config = config.get_variable(var_name)

            if var_config:
                # Find surrounding context for each usage
                pattern = r".{0,20}\{\{\s*" + re.escape(var_name) + r"\s*\}\}.{0,20}"
                matches = re.findall(pattern, all_content, re.DOTALL)

                for match in matches:
                    # Check if variable appears standalone without context
                    stripped = match.strip()
                    var_pattern = r"^\{\{\s*" + re.escape(var_name) + r"\s*\}\}$"
                    if re.match(var_pattern, stripped):
                        msg = f"Variable '{var_name}' appears without context"
                        sug = f"Add context like '{var_name}: {{{{ {var_name} }}}}'"
                        result.add_issue(
                            SemanticIssue(
                                type=SemanticIssueType.PLACEHOLDER_QUALITY,
                                severity="info",
                                message=msg,
                                location="template",
                                suggestion=sug,
                            )
                        )
                        break  # Only report once per variable

    def _check_prompt_structure(
        self, config: TemplateConfig, result: SemanticValidationResult
    ) -> None:
        """Check overall prompt structure quality."""
        # Check for appropriate use of system_prompt vs user_prompt
        if config.system_prompt and not config.user_prompt:
            result.add_issue(
                SemanticIssue(
                    type=SemanticIssueType.PROMPT_STRUCTURE,
                    severity="info",
                    message="system_prompt defined but user_prompt is empty",
                    location="user_prompt",
                    suggestion="Add user_prompt for complete chat structure",
                )
            )

        # Check for very long single prompts without structure
        all_content = (
            (config.system_prompt or "")
            + (config.user_prompt or "")
            + (config.template or "")
        )

        if len(all_content) > 3000 and not config.system_prompt:
            # Check if it has some structure
            has_structure = any(
                [
                    "<" in all_content and ">" in all_content,  # XML tags
                    "##" in all_content or "===" in all_content,  # Sections
                ]
            )
            if not has_structure:
                result.add_issue(
                    SemanticIssue(
                        type=SemanticIssueType.PROMPT_STRUCTURE,
                        severity="info",
                        message="Long template without clear structure",
                        location="template",
                        suggestion="Split into system/user prompts or add sections",
                    )
                )
