"""Tests for semantic validation."""


from prompt_template import Template
from prompt_template.semantic import (
    SemanticIssue,
    SemanticIssueType,
    SemanticValidationResult,
    SemanticValidator,
)


class TestSemanticValidationResult:
    """Tests for SemanticValidationResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        result = SemanticValidationResult()
        assert result.is_valid is True
        assert result.issues == []
        assert result.role_clarity_score == 100
        assert result.instruction_clarity_score == 100
        assert result.context_coherence_score == 100
        assert result.task_alignment_score == 100

    def test_add_warning_issue(self) -> None:
        """Test adding a warning issue."""
        result = SemanticValidationResult()
        result.add_issue(
            SemanticIssue(
                type=SemanticIssueType.ROLE_CONFUSION,
                severity="warning",
                message="Test warning",
                location="system_prompt",
            )
        )
        assert result.is_valid is True  # Warnings don't affect validity
        assert len(result.issues) == 1

    def test_add_error_issue(self) -> None:
        """Test adding an error issue."""
        result = SemanticValidationResult()
        result.add_issue(
            SemanticIssue(
                type=SemanticIssueType.ROLE_CONFUSION,
                severity="error",
                message="Test error",
                location="system_prompt",
            )
        )
        assert result.is_valid is False
        assert len(result.issues) == 1

    def test_to_validation_result(self) -> None:
        """Test conversion to ValidationResult."""
        result = SemanticValidationResult()
        result.add_issue(
            SemanticIssue(
                type=SemanticIssueType.ROLE_CONFUSION,
                severity="warning",
                message="Test warning",
                location="system_prompt",
                suggestion="Add role definition",
            )
        )
        result.add_issue(
            SemanticIssue(
                type=SemanticIssueType.INSTRUCTION_CLARITY,
                severity="info",
                message="Test info",
                location="template",
            )
        )

        validation_result = result.to_validation_result()
        assert validation_result.is_valid is True
        assert len(validation_result.warnings) == 2
        assert any("Semantic" in w for w in validation_result.warnings)


class TestSemanticValidator:
    """Tests for SemanticValidator class."""

    def test_detect_role_definition_you_are(self) -> None:
        """Test detection of 'You are' role definition."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "system_prompt": "You are a helpful assistant.",
            "user_prompt": "Help me.",
        })

        result = validator.validate(template.config)
        assert result.role_clarity_score >= 80

    def test_detect_role_definition_act_as(self) -> None:
        """Test detection of 'Act as' role definition."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "template": "Act as a professional writer. Write about {{topic}}.",
            "variables": [{"name": "topic", "type": "string"}],
        })

        result = validator.validate(template.config)
        assert result.role_clarity_score >= 80

    def test_detect_role_definition_xml_tag(self) -> None:
        """Test detection of <role> XML tag."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "template": "<role>Expert coder</role>\nHelp with {{task}}.",
            "variables": [{"name": "task", "type": "string"}],
        })

        result = validator.validate(template.config)
        assert result.role_clarity_score >= 80

    def test_missing_role_definition(self) -> None:
        """Test warning for missing role definition."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "template": "Do the task: {{task}}",
            "variables": [{"name": "task", "type": "string"}],
        })

        result = validator.validate(template.config)
        assert result.role_clarity_score < 100

        # Should have an issue about missing role
        role_issues = [
            i for i in result.issues if i.type == SemanticIssueType.ROLE_CONFUSION
        ]
        assert len(role_issues) > 0

    def test_role_in_wrong_place(self) -> None:
        """Test warning when role is in user_prompt instead of system_prompt."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "system_prompt": "Some general instructions.",
            "user_prompt": "You are an expert. Help me with {{task}}.",
            "variables": [{"name": "task", "type": "string"}],
        })

        result = validator.validate(template.config)

        # Should detect role in wrong place
        role_issues = [
            i for i in result.issues if i.type == SemanticIssueType.ROLE_CONFUSION
        ]
        assert any("user_prompt" in i.location for i in role_issues)

    def test_detect_task_instructions(self) -> None:
        """Test detection of task instructions."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "template": "Your task is to summarize {{text}}.",
            "variables": [{"name": "text", "type": "string"}],
        })

        result = validator.validate(template.config)
        # Should have good instruction clarity with task pattern
        assert result.instruction_clarity_score >= 60

    def test_detect_output_format(self) -> None:
        """Test detection of output format specification."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "template": """
            You are an assistant.
            <output_format>
            Respond in JSON format.
            </output_format>
            Do: {{task}}
            """,
            "variables": [{"name": "task", "type": "string"}],
        })

        result = validator.validate(template.config)
        # Should recognize output format
        assert result.instruction_clarity_score >= 70

    def test_detect_ambiguous_language(self) -> None:
        """Test detection of ambiguous language."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "template": """
            You are an assistant.
            Maybe do this. Perhaps try that. You might want to consider this.
            Task: {{task}}
            """,
            "variables": [{"name": "task", "type": "string"}],
        })

        result = validator.validate(template.config)

        # Should detect ambiguous phrases
        clarity_issues = [
            i for i in result.issues if i.type == SemanticIssueType.INSTRUCTION_CLARITY
        ]
        assert any("ambiguous" in i.message.lower() for i in clarity_issues)

    def test_detect_content_duplication(self) -> None:
        """Test detection of content duplication between prompts."""
        validator = SemanticValidator()

        duplicated_sentence = (
            "This is a very specific instruction that appears in both places "
            "and should be detected as duplicate content in semantic validation."
        )

        template = Template.from_dict({
            "name": "test",
            "system_prompt": f"You are an assistant. {duplicated_sentence}",
            "user_prompt": f"Help me. {duplicated_sentence}",
        })

        result = validator.validate(template.config)

        # Should detect duplication
        coherence_issues = [
            i for i in result.issues if i.type == SemanticIssueType.CONTEXT_COHERENCE
        ]
        assert len(coherence_issues) > 0

    def test_missing_description(self) -> None:
        """Test detection of missing template description."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "template": "Do {{task}}",
            "variables": [{"name": "task", "type": "string"}],
        })

        result = validator.validate(template.config)

        # Should note missing description
        alignment_issues = [
            i for i in result.issues if i.type == SemanticIssueType.TASK_ALIGNMENT
        ]
        assert any("description" in i.message.lower() for i in alignment_issues)

    def test_system_prompt_without_user_prompt(self) -> None:
        """Test warning for system_prompt without user_prompt."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "system_prompt": "You are an assistant.",
        })

        result = validator.validate(template.config)

        # Should suggest adding user_prompt
        structure_issues = [
            i for i in result.issues if i.type == SemanticIssueType.PROMPT_STRUCTURE
        ]
        assert any("user_prompt" in i.message.lower() for i in structure_issues)

    def test_placeholder_quality_standalone(self) -> None:
        """Test detection of standalone placeholders without context."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "test",
            "template": "{{code}}",  # Just a variable, no context
            "variables": [{"name": "code", "type": "string"}],
        })

        result = validator.validate(template.config)

        # Should suggest adding context
        placeholder_issues = [
            i for i in result.issues if i.type == SemanticIssueType.PLACEHOLDER_QUALITY
        ]
        assert len(placeholder_issues) > 0

    def test_good_template_high_scores(self) -> None:
        """Test that a well-structured template gets high scores."""
        validator = SemanticValidator()

        template = Template.from_dict({
            "name": "code-reviewer",
            "description": "Reviews code for bugs and improvements",
            "system_prompt": """
            You are an expert code reviewer.
            Your task is to analyze code for issues.
            """,
            "user_prompt": """
            Please review this code:

            <code>
            {{code}}
            </code>

            <output_format>
            Provide a structured review with:
            1. Issues found
            2. Suggestions
            </output_format>
            """,
            "variables": [
                {
                    "name": "code",
                    "type": "string",
                    "description": "The code to review",
                }
            ],
        })

        result = validator.validate(template.config)

        # Should have high scores
        assert result.role_clarity_score >= 80
        assert result.instruction_clarity_score >= 60
        assert result.context_coherence_score >= 80
        assert result.task_alignment_score >= 80
