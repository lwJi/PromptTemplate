"""Tests for template analysis and token counting."""


from prompt_template import Template
from prompt_template.analyzer import TemplateAnalyzer, TokenCounter, get_model_limit
from prompt_template.models import VariableConfig, VariableType


class TestTokenCounter:
    """Tests for TokenCounter class."""

    def test_count_simple_text(self) -> None:
        """Test counting tokens in simple text."""
        counter = TokenCounter(use_tiktoken=False)  # Use fallback
        count = counter.count_tokens("Hello, world!")
        assert count > 0
        assert count < 20

    def test_count_empty_text(self) -> None:
        """Test counting tokens in empty text."""
        counter = TokenCounter(use_tiktoken=False)
        count = counter.count_tokens("")
        assert count == 0

    def test_count_longer_text(self) -> None:
        """Test counting tokens in longer text."""
        counter = TokenCounter(use_tiktoken=False)
        text = "This is a longer piece of text that should have more tokens."
        count = counter.count_tokens(text)
        assert count > 5

    def test_estimate_variable_tokens_with_default(self) -> None:
        """Test estimating tokens for variable with default."""
        counter = TokenCounter(use_tiktoken=False)
        var = VariableConfig(
            name="greeting",
            type=VariableType.STRING,
            default="Hello, world!",
        )

        estimate = counter.estimate_variable_tokens(var)
        assert estimate > 0

    def test_estimate_variable_tokens_with_sample(self) -> None:
        """Test estimating tokens with sample values."""
        counter = TokenCounter(use_tiktoken=False)
        var = VariableConfig(name="text", type=VariableType.STRING)

        estimate = counter.estimate_variable_tokens(
            var, sample_values={"text": "This is sample text"}
        )
        assert estimate > 0

    def test_estimate_variable_tokens_by_type(self) -> None:
        """Test estimating tokens based on variable type."""
        counter = TokenCounter(use_tiktoken=False)

        int_var = VariableConfig(name="count", type=VariableType.INTEGER)
        string_var = VariableConfig(name="text", type=VariableType.STRING)
        list_var = VariableConfig(name="items", type=VariableType.LIST)

        int_estimate = counter.estimate_variable_tokens(int_var)
        string_estimate = counter.estimate_variable_tokens(string_var)
        list_estimate = counter.estimate_variable_tokens(list_var)

        # List should typically estimate higher than integer
        assert list_estimate > int_estimate
        # String should be in between
        assert string_estimate >= int_estimate

    def test_estimate_variable_tokens_with_description_hint(self) -> None:
        """Test that description hints affect estimation."""
        counter = TokenCounter(use_tiktoken=False)

        short_var = VariableConfig(
            name="text",
            type=VariableType.STRING,
            description="A short label",
        )
        long_var = VariableConfig(
            name="content",
            type=VariableType.STRING,
            description="The full code content to analyze",
        )

        short_estimate = counter.estimate_variable_tokens(short_var)
        long_estimate = counter.estimate_variable_tokens(long_var)

        # Long content description should estimate higher
        assert long_estimate > short_estimate

    def test_tiktoken_available_property(self) -> None:
        """Test tiktoken_available property."""
        counter = TokenCounter(use_tiktoken=False)
        # Should work regardless of tiktoken availability
        assert isinstance(counter.tiktoken_available, bool)


class TestGetModelLimit:
    """Tests for get_model_limit function."""

    def test_exact_match(self) -> None:
        """Test exact model name match."""
        assert get_model_limit("gpt-4") == 8192
        assert get_model_limit("gpt-4-turbo") == 128000
        assert get_model_limit("claude-3-sonnet") == 200000

    def test_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        assert get_model_limit("GPT-4") == 8192
        assert get_model_limit("Claude-3-Sonnet") == 200000

    def test_unknown_model_returns_default(self) -> None:
        """Test unknown model returns default limit."""
        limit = get_model_limit("unknown-model-xyz")
        assert limit == 8192  # default


class TestTemplateAnalyzer:
    """Tests for TemplateAnalyzer class."""

    def test_analyze_simple_template(self) -> None:
        """Test analyzing a simple template."""
        template = Template.from_dict({
            "name": "test",
            "template": "Hello, {{name}}!",
            "variables": [{"name": "name", "type": "string", "required": True}],
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(template.config)

        assert result.template_name == "test"
        assert result.token_estimate.total_static_tokens > 0
        assert "name" in result.variable_analysis

    def test_analyze_template_with_system_user(self) -> None:
        """Test analyzing template with system/user prompts."""
        template = Template.from_dict({
            "name": "test",
            "system_prompt": "You are a helpful assistant.",
            "user_prompt": "Help me with {{task}}",
            "variables": [{"name": "task", "type": "string", "required": True}],
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(template.config)

        assert result.token_estimate.system_prompt_tokens is not None
        assert result.token_estimate.user_prompt_tokens is not None
        assert result.structural_analysis.has_system_prompt
        assert result.structural_analysis.has_user_prompt

    def test_analyze_model_fit(self) -> None:
        """Test model fit analysis."""
        template = Template.from_dict({
            "name": "test",
            "template": "Short template",
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(
            template.config, target_models=["gpt-4", "gpt-4-turbo"]
        )

        assert "gpt-4" in result.token_estimate.model_fit
        assert "gpt-4-turbo" in result.token_estimate.model_fit
        # Short template should fit in both
        assert result.token_estimate.model_fit["gpt-4"] is True
        assert result.token_estimate.model_fit["gpt-4-turbo"] is True

    def test_analyze_detects_conditionals(self) -> None:
        """Test detection of conditionals in template."""
        template = Template.from_dict({
            "name": "test",
            "template": "{% if verbose %}Detailed{% else %}Brief{% endif %} output",
            "variables": [{"name": "verbose", "type": "boolean"}],
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(template.config)

        assert result.structural_analysis.uses_conditionals is True
        assert result.structural_analysis.nesting_depth >= 1

    def test_analyze_detects_loops(self) -> None:
        """Test detection of loops in template."""
        template = Template.from_dict({
            "name": "test",
            "template": "{% for item in items %}{{item}}{% endfor %}",
            "variables": [{"name": "items", "type": "list"}],
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(template.config)

        assert result.structural_analysis.uses_loops is True

    def test_analyze_variable_analysis(self) -> None:
        """Test variable analysis details."""
        template = Template.from_dict({
            "name": "test",
            "system_prompt": "You are {{role}}.",
            "user_prompt": "Do {{task}}. The {{role}} should help.",
            "variables": [
                {
                    "name": "role",
                    "type": "string",
                    "description": "The assistant role to play in conversation",
                },
                {"name": "task", "type": "string"},
            ],
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(template.config)

        assert "role" in result.variable_analysis
        assert "task" in result.variable_analysis

        role_analysis = result.variable_analysis["role"]
        assert role_analysis.usage_count == 2  # Used twice
        assert role_analysis.in_system_prompt is True
        assert role_analysis.in_user_prompt is True
        assert role_analysis.description_quality == "good"  # > 20 chars

        task_analysis = result.variable_analysis["task"]
        assert task_analysis.description_quality == "missing"

    def test_recommendations_for_missing_description(self) -> None:
        """Test that recommendations are generated for missing variable descriptions."""
        template = Template.from_dict({
            "name": "test",
            "template": "Hello, {{name}}!",
            "variables": [{"name": "name", "type": "string"}],
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(template.config)

        # Should have recommendation about variable description
        assert any("description" in r.lower() for r in result.recommendations)

    def test_recommendations_for_missing_template_description(self) -> None:
        """Test recommendations for missing template description."""
        template = Template.from_dict({
            "name": "test",
            "template": "Hello!",
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(template.config)

        assert any("description" in r.lower() for r in result.recommendations)

    def test_analyze_counts_sections(self) -> None:
        """Test section counting in structural analysis."""
        template = Template.from_dict({
            "name": "test",
            "template": """<role>You are an assistant</role>
<task>Do something</task>
## Instructions
Follow these steps.
""",
        })

        analyzer = TemplateAnalyzer()
        result = analyzer.analyze(template.config)

        # Should count XML tags (2 opening tags) and markdown headers (1)
        assert result.structural_analysis.section_count >= 3
