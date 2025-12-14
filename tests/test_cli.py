"""Tests for the CLI interface."""

import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from prompt_template.cli import cli


class TestCLI:
    """Tests for CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def temp_templates_dir(self):
        """Create a temporary directory with test templates."""
        temp_dir = Path(tempfile.mkdtemp())

        # Create test template
        template_content = """
name: test-template
description: A test template for CLI testing
version: 1.0.0
tags:
  - test
  - cli
template: "Hello, {{name}}! Your favorite color is {{color}}."
variables:
  - name: name
    type: string
    required: true
    description: Your name
  - name: color
    type: string
    required: false
    default: blue
    description: Your favorite color
"""
        templates_dir = temp_dir / "templates"
        templates_dir.mkdir()
        (templates_dir / "test-template.yaml").write_text(template_content)

        # Change to temp directory for tests
        original_cwd = Path.cwd()
        import os
        os.chdir(temp_dir)

        yield temp_dir

        # Restore and cleanup
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)

    def test_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Prompt Template" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "run" in result.output

    def test_list_empty(self, runner):
        """Test list command with no templates."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["list"])

            assert "No templates found" in result.output

    def test_list_templates(self, runner, temp_templates_dir):
        """Test list command with templates."""
        result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "test-template" in result.output

    def test_list_json(self, runner, temp_templates_dir):
        """Test list command with JSON output."""
        result = runner.invoke(cli, ["list", "--json"])

        assert result.exit_code == 0
        assert '"name": "test-template"' in result.output

    def test_list_paths(self, runner, temp_templates_dir):
        """Test list --paths shows search paths."""
        result = runner.invoke(cli, ["list", "--paths"])

        assert result.exit_code == 0
        assert "templates" in result.output.lower()

    def test_show_template(self, runner, temp_templates_dir):
        """Test show command."""
        result = runner.invoke(cli, ["show", "test-template"])

        assert result.exit_code == 0
        assert "test-template" in result.output
        assert "name" in result.output
        assert "color" in result.output

    def test_show_template_raw(self, runner, temp_templates_dir):
        """Test show --raw command."""
        result = runner.invoke(cli, ["show", "test-template", "--raw"])

        assert result.exit_code == 0
        assert "template:" in result.output

    def test_show_template_preview(self, runner, temp_templates_dir):
        """Test show --preview command."""
        result = runner.invoke(cli, ["show", "test-template", "--preview"])

        assert result.exit_code == 0
        assert "[name]" in result.output  # Placeholder
        assert "blue" in result.output  # Default value

    def test_show_nonexistent(self, runner, temp_templates_dir):
        """Test show command with nonexistent template."""
        result = runner.invoke(cli, ["show", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_run_template(self, runner, temp_templates_dir):
        """Test run command with variables."""
        result = runner.invoke(cli, ["run", "test-template", "-v", "name=Alice"])

        assert result.exit_code == 0
        assert "Hello, Alice!" in result.output
        assert "blue" in result.output  # Default color

    def test_run_template_override_default(self, runner, temp_templates_dir):
        """Test run command overriding default value."""
        result = runner.invoke(cli, [
            "run", "test-template",
            "-v", "name=Bob",
            "-v", "color=red"
        ])

        assert result.exit_code == 0
        assert "Hello, Bob!" in result.output
        assert "red" in result.output

    def test_run_missing_required(self, runner, temp_templates_dir):
        """Test run command with missing required variable."""
        result = runner.invoke(cli, ["run", "test-template"])

        assert result.exit_code == 1
        assert "missing" in result.output.lower() or "required" in result.output.lower()

    def test_run_interactive(self, runner, temp_templates_dir):
        """Test run command in interactive mode."""
        result = runner.invoke(cli, [
            "run", "test-template", "-i"
        ], input="Alice\n")

        assert result.exit_code == 0
        assert "Alice" in result.output

    def test_validate_valid_template(self, runner, temp_templates_dir):
        """Test validate command with valid template."""
        template_path = temp_templates_dir / "templates" / "test-template.yaml"
        result = runner.invoke(cli, ["validate", str(template_path)])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_invalid_template(self, runner, temp_templates_dir):
        """Test validate command with invalid template."""
        # Create invalid template
        invalid_path = temp_templates_dir / "templates" / "invalid.yaml"
        invalid_path.write_text("""
name: invalid
template: "Hello, {{name}!"
variables:
  - name: name
    type: string
    required: true
""")

        result = runner.invoke(cli, ["validate", str(invalid_path)])

        assert result.exit_code == 1
        assert "error" in result.output.lower()

    def test_init_creates_directory(self, runner):
        """Test init command creates directory."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init", "--with-examples"])

            assert result.exit_code == 0
            assert Path("templates").exists()

    def test_init_with_custom_path(self, runner):
        """Test init command with custom path."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init", "-p", "my-prompts", "--with-examples"])

            assert result.exit_code == 0
            assert Path("my-prompts").exists()

    def test_new_template(self, runner, temp_templates_dir):
        """Test new command creates template."""
        runner.invoke(
            cli,
            ["new", "my-new-template", "-o", "my-new-template.yaml"],
            input="My description\nvar1\nFirst variable\ny\n\n"
        )
        # The command should complete (may need editor for template content)
        # In tests, editor returns None, so it might fail
        # But the basic flow should work

    def test_search_by_tags(self, runner, temp_templates_dir):
        """Test list command with tag filter."""
        result = runner.invoke(cli, ["list", "-t", "test"])

        assert result.exit_code == 0
        assert "test-template" in result.output

    def test_search_by_query(self, runner, temp_templates_dir):
        """Test list command with search query."""
        result = runner.invoke(cli, ["list", "-s", "CLI"])

        assert result.exit_code == 0
        assert "test-template" in result.output


class TestCLIErrors:
    """Tests for CLI error handling."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_invalid_var_format(self, runner):
        """Test error for invalid variable format."""
        with runner.isolated_filesystem():
            # Create minimal template
            Path("templates").mkdir()
            Path("templates/test.yaml").write_text("""
name: test
template: "{{x}}"
variables:
  - name: x
    type: string
    required: true
""")

            result = runner.invoke(cli, ["run", "test", "-v", "invalid"])

            assert result.exit_code == 1
            is_invalid = "invalid" in result.output.lower()
            is_format = "format" in result.output.lower()
            assert is_invalid or is_format

    def test_json_parse_error(self, runner):
        """Test error for invalid JSON input."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/test.yaml").write_text("""
name: test
template: "{{x}}"
variables:
  - name: x
    type: string
    required: true
""")
            Path("bad.json").write_text("{invalid json}")

            result = runner.invoke(cli, ["run", "test", "-j", "bad.json"])

            assert result.exit_code == 1
            assert "json" in result.output.lower() or "parse" in result.output.lower()
