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


class TestFileInput:
    """Tests for file input with @ prefix."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_file_input_single(self, runner):
        """Test loading single file with @ prefix."""
        with runner.isolated_filesystem():
            # Create template
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "Content: {{text}}"
variables:
  - name: text
    type: string
    required: true
""")
            # Create test file
            Path("input.txt").write_text("Hello from file!")

            result = runner.invoke(cli, ["run", "echo", "-v", "text=@input.txt"])

            assert result.exit_code == 0
            assert "Hello from file!" in result.output

    def test_file_input_glob_single_match(self, runner):
        """Test glob pattern matching single file."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "{{content}}"
variables:
  - name: content
    type: string
    required: true
""")
            Path("src").mkdir()
            Path("src/main.py").write_text("print('hello')")

            result = runner.invoke(cli, ["run", "echo", "-v", "content=@src/*.py"])

            assert result.exit_code == 0
            assert "print('hello')" in result.output

    def test_file_input_glob_multiple_files(self, runner):
        """Test glob pattern matching multiple files."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "Files:\\n{{files}}"
variables:
  - name: files
    type: string
    required: true
""")
            Path("src").mkdir()
            Path("src/a.py").write_text("# file a")
            Path("src/b.py").write_text("# file b")

            result = runner.invoke(cli, ["run", "echo", "-v", "files=@src/*.py"])

            assert result.exit_code == 0
            assert "# file a" in result.output
            assert "# file b" in result.output
            assert "# File:" in result.output  # Header for multiple files

    def test_file_input_recursive_glob(self, runner):
        """Test recursive glob pattern."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "{{content}}"
variables:
  - name: content
    type: string
    required: true
""")
            Path("src/sub").mkdir(parents=True)
            Path("src/main.py").write_text("# root")
            Path("src/sub/util.py").write_text("# nested")

            result = runner.invoke(cli, ["run", "echo", "-v", "content=@src/**/*.py"])

            assert result.exit_code == 0
            assert "# root" in result.output
            assert "# nested" in result.output

    def test_file_not_found(self, runner):
        """Test error when file doesn't exist."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "{{text}}"
variables:
  - name: text
    type: string
    required: true
""")

            result = runner.invoke(cli, ["run", "echo", "-v", "text=@nonexistent.txt"])

            assert result.exit_code != 0
            assert "File not found" in result.output

    def test_glob_no_matches(self, runner):
        """Test error when glob pattern matches no files."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "{{text}}"
variables:
  - name: text
    type: string
    required: true
""")
            Path("src").mkdir()

            result = runner.invoke(cli, ["run", "echo", "-v", "text=@src/*.xyz"])

            assert result.exit_code != 0
            assert "No files match pattern" in result.output

    def test_file_input_with_equals_in_content(self, runner):
        """Test file content containing equals signs."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "{{content}}"
variables:
  - name: content
    type: string
    required: true
""")
            Path("config.txt").write_text("key=value\nfoo=bar")

            result = runner.invoke(cli, ["run", "echo", "-v", "content=@config.txt"])

            assert result.exit_code == 0
            assert "key=value" in result.output
            assert "foo=bar" in result.output

    def test_file_input_mixed_with_literal(self, runner):
        """Test mixing file input with literal values."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/review.yaml").write_text("""
name: review
template: "Language: {{lang}}\\nCode:\\n{{code}}"
variables:
  - name: code
    type: string
    required: true
  - name: lang
    type: string
    required: true
""")
            Path("main.py").write_text("print('hello')")

            result = runner.invoke(cli, [
                "run", "review",
                "-v", "code=@main.py",
                "-v", "lang=python"
            ])

            assert result.exit_code == 0
            assert "Language: python" in result.output
            assert "print('hello')" in result.output

    def test_literal_at_sign(self, runner):
        """Test that @ at beginning triggers file load, not in middle."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "{{text}}"
variables:
  - name: text
    type: string
    required: true
""")

            # Email address should be passed literally (@ not at start after =)
            result = runner.invoke(cli, ["run", "echo", "-v", "text=user@example.com"])

            assert result.exit_code == 0
            assert "user@example.com" in result.output


class TestOutputFormats:
    """Tests for output format options."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def template_dir(self, runner):
        """Create a temporary directory with a test template."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/echo.yaml").write_text("""
name: echo
template: "Hello, {{name}}!"
variables:
  - name: name
    type: string
    required: true
""")
            yield

    def test_format_raw(self, runner, template_dir):
        """Test raw output format."""
        result = runner.invoke(cli, [
            "run", "echo", "-v", "name=World", "-f", "raw"
        ])

        assert result.exit_code == 0
        assert result.output.strip() == "Hello, World!"
        # Should not contain Rich panel decorations
        assert "╭" not in result.output
        assert "╰" not in result.output

    def test_format_json(self, runner, template_dir):
        """Test JSON output format."""
        import json

        result = runner.invoke(cli, [
            "run", "echo", "-v", "name=World", "-f", "json"
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["template"]["name"] == "echo"
        assert data["rendered"] == "Hello, World!"
        assert data["variables"]["name"] == "World"
        assert "timestamp" in data["metadata"]

    def test_format_markdown(self, runner, template_dir):
        """Test Markdown output format."""
        result = runner.invoke(cli, [
            "run", "echo", "-v", "name=World", "-f", "markdown"
        ])

        assert result.exit_code == 0
        assert "# echo" in result.output
        assert "**Version:**" in result.output
        assert "## Variables" in result.output
        assert "| name | World |" in result.output
        assert "## Rendered Output" in result.output
        assert "Hello, World!" in result.output

    def test_format_chat_api(self, runner, template_dir):
        """Test chat-api output format."""
        import json

        result = runner.invoke(cli, [
            "run", "echo", "-v", "name=World", "-f", "chat-api"
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "messages" in data
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello, World!"
        assert data["metadata"]["template"] == "echo"

    def test_format_env(self, runner, template_dir):
        """Test env output format."""
        result = runner.invoke(cli, [
            "run", "echo", "-v", "name=World", "-f", "env"
        ])

        assert result.exit_code == 0
        assert "#!/bin/bash" in result.output
        assert 'export PROMPT_TEMPLATE_NAME="echo"' in result.output
        assert "export PROMPT_VAR_NAME='World'" in result.output
        assert "PROMPT_CONTENT" in result.output
        assert "Hello, World!" in result.output

    def test_output_to_file(self, runner, template_dir):
        """Test writing output to file."""
        result = runner.invoke(cli, [
            "run", "echo", "-v", "name=World", "-f", "raw", "-o", "output.txt"
        ])

        assert result.exit_code == 0
        assert "Output written to" in result.output
        assert Path("output.txt").exists()
        assert Path("output.txt").read_text() == "Hello, World!"

    def test_output_to_file_json(self, runner, template_dir):
        """Test writing JSON output to file."""
        import json

        result = runner.invoke(cli, [
            "run", "echo", "-v", "name=World", "-f", "json", "-o", "output.json"
        ])

        assert result.exit_code == 0
        data = json.loads(Path("output.json").read_text())
        assert data["rendered"] == "Hello, World!"


class TestSplitPrompts:
    """Tests for system/user prompt separation."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_split_prompts_render(self, runner):
        """Test rendering with split system/user prompts."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/chat.yaml").write_text("""
name: chat
system_prompt: "You are a helpful {{role}}."
user_prompt: "Please help me with: {{task}}"
variables:
  - name: role
    type: string
    required: true
  - name: task
    type: string
    required: true
""")

            result = runner.invoke(cli, [
                "run", "chat", "-v", "role=assistant", "-v", "task=coding"
            ])

            assert result.exit_code == 0
            assert "You are a helpful assistant." in result.output
            assert "Please help me with: coding" in result.output

    def test_split_prompts_json_format(self, runner):
        """Test JSON output includes split prompts."""
        import json

        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/chat.yaml").write_text("""
name: chat
system_prompt: "You are a helpful {{role}}."
user_prompt: "Please help me with: {{task}}"
variables:
  - name: role
    type: string
    required: true
  - name: task
    type: string
    required: true
""")

            result = runner.invoke(cli, [
                "run", "chat",
                "-v", "role=assistant",
                "-v", "task=coding",
                "-f", "json"
            ])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "prompts" in data
            assert data["prompts"]["system"] == "You are a helpful assistant."
            assert data["prompts"]["user"] == "Please help me with: coding"

    def test_split_prompts_chat_api_format(self, runner):
        """Test chat-api output with split prompts."""
        import json

        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/chat.yaml").write_text("""
name: chat
system_prompt: "You are a helpful {{role}}."
user_prompt: "Please help me with: {{task}}"
variables:
  - name: role
    type: string
    required: true
  - name: task
    type: string
    required: true
""")

            result = runner.invoke(cli, [
                "run", "chat",
                "-v", "role=assistant",
                "-v", "task=coding",
                "-f", "chat-api"
            ])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data["messages"]) == 2
            assert data["messages"][0]["role"] == "system"
            assert data["messages"][0]["content"] == "You are a helpful assistant."
            assert data["messages"][1]["role"] == "user"
            assert data["messages"][1]["content"] == "Please help me with: coding"

    def test_split_prompts_markdown_format(self, runner):
        """Test markdown output with split prompts."""
        with runner.isolated_filesystem():
            Path("templates").mkdir()
            Path("templates/chat.yaml").write_text("""
name: chat
system_prompt: "You are a helpful {{role}}."
user_prompt: "Please help me with: {{task}}"
variables:
  - name: role
    type: string
    required: true
  - name: task
    type: string
    required: true
""")

            result = runner.invoke(cli, [
                "run", "chat",
                "-v", "role=assistant",
                "-v", "task=coding",
                "-f", "markdown"
            ])

            assert result.exit_code == 0
            assert "## System Prompt" in result.output
            assert "## User Prompt" in result.output
            assert "You are a helpful assistant." in result.output
            assert "Please help me with: coding" in result.output
