"""Tests for the Template class."""

import tempfile

import pytest

from prompt_template import (
    Template,
    TemplateConfig,
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateValidationError,
    VariableConfig,
    VariableType,
)


class TestTemplateCreation:
    """Tests for template creation."""

    def test_create_from_config(self):
        """Test creating template from TemplateConfig."""
        config = TemplateConfig(
            name="test-template",
            template="Hello, {{name}}!",
            variables=[
                VariableConfig(name="name", type=VariableType.STRING, required=True)
            ],
        )
        template = Template(config)

        assert template.name == "test-template"
        assert len(template.variables) == 1

    def test_create_from_dict(self):
        """Test creating template from dictionary."""
        data = {
            "name": "greeting",
            "template": "Hello, {{name}}!",
            "variables": [{"name": "name", "type": "string", "required": True}],
        }
        template = Template.from_dict(data)

        assert template.name == "greeting"
        assert template.template_content == "Hello, {{name}}!"

    def test_create_from_string(self):
        """Test creating template from YAML string."""
        yaml_content = """
name: my-template
description: A test template
template: "Hello, {{name}}!"
variables:
  - name: name
    type: string
    required: true
"""
        template = Template.from_string(yaml_content)

        assert template.name == "my-template"
        assert template.description == "A test template"

    def test_create_from_file(self):
        """Test creating template from file."""
        yaml_content = """
name: file-template
template: "Hello from file!"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            template = Template.from_file(f.name)
            assert template.name == "file-template"

    def test_file_not_found_error(self):
        """Test error when file doesn't exist."""
        with pytest.raises(TemplateNotFoundError) as exc_info:
            Template.from_file("/nonexistent/path/template.yaml")

        assert "not found" in str(exc_info.value).lower()

    def test_invalid_yaml_error(self):
        """Test error for invalid YAML."""
        invalid_yaml = "name: test\n  bad: indentation"

        with pytest.raises(TemplateValidationError):
            Template.from_string(invalid_yaml)

    def test_missing_required_fields(self):
        """Test error when required fields are missing."""
        with pytest.raises(TemplateValidationError):
            Template.from_dict({"description": "No name or template"})


class TestTemplateRendering:
    """Tests for template rendering."""

    def test_simple_render(self):
        """Test basic variable substitution."""
        template = Template.from_dict({
            "name": "greeting",
            "template": "Hello, {{name}}!",
            "variables": [{"name": "name", "type": "string", "required": True}],
        })

        result = template.render(name="World")
        assert result == "Hello, World!"

    def test_render_with_defaults(self):
        """Test rendering with default values."""
        template = Template.from_dict({
            "name": "greeting",
            "template": "Hello, {{name}}! Style: {{style}}",
            "variables": [
                {"name": "name", "type": "string", "required": True},
                {
                    "name": "style",
                    "type": "string",
                    "required": False,
                    "default": "formal",
                },
            ],
        })

        result = template.render(name="World")
        assert result == "Hello, World! Style: formal"

    def test_render_override_default(self):
        """Test overriding default values."""
        template = Template.from_dict({
            "name": "greeting",
            "template": "Style: {{style}}",
            "variables": [
                {
                    "name": "style",
                    "type": "string",
                    "required": False,
                    "default": "formal",
                },
            ],
        })

        result = template.render(style="casual")
        assert result == "Style: casual"

    def test_render_missing_required_variable(self):
        """Test error when required variable is missing."""
        template = Template.from_dict({
            "name": "greeting",
            "template": "Hello, {{name}}!",
            "variables": [{"name": "name", "type": "string", "required": True}],
        })

        with pytest.raises(TemplateRenderError) as exc_info:
            template.render()

        error_msg = str(exc_info.value).lower()
        assert "missing" in error_msg or "required" in error_msg

    def test_render_with_conditionals(self):
        """Test rendering with Jinja2 conditionals."""
        template_str = (
            "{% if formal %}Dear {{name}},{% else %}Hi {{name}}!{% endif %}"
        )
        template = Template.from_dict({
            "name": "conditional",
            "template": template_str,
            "variables": [
                {"name": "name", "type": "string", "required": True},
                {
                    "name": "formal",
                    "type": "boolean",
                    "required": False,
                    "default": False,
                },
            ],
        })

        formal_result = template.render(name="Alice", formal=True)
        assert formal_result == "Dear Alice,"

        casual_result = template.render(name="Bob", formal=False)
        assert casual_result == "Hi Bob!"

    def test_render_with_loops(self):
        """Test rendering with Jinja2 loops."""
        template_str = (
            "Items: {% for item in items %}"
            "{{item}}{% if not loop.last %}, {% endif %}"
            "{% endfor %}"
        )
        template = Template.from_dict({
            "name": "list-template",
            "template": template_str,
            "variables": [{"name": "items", "type": "list", "required": True}],
        })

        result = template.render(items=["apple", "banana", "cherry"])
        assert result == "Items: apple, banana, cherry"

    def test_render_with_filters(self):
        """Test rendering with Jinja2 filters."""
        template = Template.from_dict({
            "name": "filter-template",
            "template": "Hello, {{name | upper}}!",
            "variables": [{"name": "name", "type": "string", "required": True}],
        })

        result = template.render(name="world")
        assert result == "Hello, WORLD!"


class TestTemplateValidation:
    """Tests for template validation."""

    def test_valid_template(self):
        """Test validation of a valid template."""
        template = Template.from_dict({
            "name": "valid",
            "template": "Hello, {{name}}!",
            "variables": [{"name": "name", "type": "string", "required": True}],
        })

        result = template.validate()
        assert result.is_valid

    def test_invalid_syntax(self):
        """Test detection of syntax errors."""
        template = Template.from_dict({
            "name": "invalid-syntax",
            "template": "Hello, {{name}!",  # Missing closing brace
            "variables": [{"name": "name", "type": "string", "required": True}],
        })

        result = template.validate()
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_unused_variable_warning(self):
        """Test warning for unused variables."""
        template = Template.from_dict({
            "name": "unused-var",
            "template": "Hello!",
            "variables": [{"name": "unused", "type": "string", "required": True}],
        })

        result = template.validate()
        assert len(result.warnings) > 0
        assert any("unused" in w.lower() for w in result.warnings)

    def test_undeclared_variable_warning(self):
        """Test warning for undeclared variables."""
        template = Template.from_dict({
            "name": "undeclared-var",
            "template": "Hello, {{unknown}}!",
            "variables": [],
        })

        result = template.validate()
        assert len(result.warnings) > 0
        assert any("unknown" in w.lower() for w in result.warnings)

    def test_enum_validation(self):
        """Test enum value validation."""
        template = Template.from_dict({
            "name": "enum-test",
            "template": "Style: {{style}}",
            "variables": [
                {
                    "name": "style",
                    "type": "string",
                    "required": True,
                    "enum": ["formal", "casual"],
                }
            ],
        })

        # Valid enum value should work
        result = template.render(style="formal")
        assert result == "Style: formal"

        # Invalid enum value should fail
        with pytest.raises(TemplateRenderError):
            template.render(style="invalid")


class TestTemplatePreview:
    """Tests for template preview functionality."""

    def test_preview_with_placeholders(self):
        """Test preview shows placeholders for missing variables."""
        template = Template.from_dict({
            "name": "preview-test",
            "template": "Hello, {{name}}! You are {{age}} years old.",
            "variables": [
                {"name": "name", "type": "string", "required": True},
                {"name": "age", "type": "integer", "required": True},
            ],
        })

        preview = template.preview()
        assert "[name]" in preview
        assert "[age]" in preview

    def test_preview_with_partial_variables(self):
        """Test preview with some variables provided."""
        template = Template.from_dict({
            "name": "preview-test",
            "template": "Hello, {{name}}! You are {{age}} years old.",
            "variables": [
                {"name": "name", "type": "string", "required": True},
                {"name": "age", "type": "integer", "required": True},
            ],
        })

        preview = template.preview(name="Alice")
        assert "Alice" in preview
        assert "[age]" in preview


class TestTemplateHelpers:
    """Tests for template helper methods."""

    def test_get_required_variables(self):
        """Test getting required variables."""
        template = Template.from_dict({
            "name": "test",
            "template": "{{a}} {{b}} {{c}}",
            "variables": [
                {"name": "a", "type": "string", "required": True},
                {"name": "b", "type": "string", "required": False, "default": "B"},
                {"name": "c", "type": "string", "required": True},
            ],
        })

        required = template.get_required_variables()
        assert "a" in required
        assert "b" not in required  # Has default
        assert "c" in required

    def test_get_all_variables(self):
        """Test getting all variables from template."""
        template = Template.from_dict({
            "name": "test",
            "template": "{{a}} {{b}} {{c}}",
            "variables": [],
        })

        all_vars = template.get_all_variables()
        assert all_vars == {"a", "b", "c"}

    def test_to_dict(self):
        """Test converting template to dictionary."""
        template = Template.from_dict({
            "name": "test",
            "description": "Test description",
            "template": "Hello!",
            "variables": [],
        })

        data = template.to_dict()
        assert data["name"] == "test"
        assert data["description"] == "Test description"
        assert data["template"] == "Hello!"
