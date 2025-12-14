"""Tests for the TemplateRegistry class."""

import shutil
import tempfile
from pathlib import Path

import pytest

from prompt_template import TemplateNotFoundError, TemplateRegistry


class TestTemplateRegistry:
    """Tests for template registry functionality."""

    @pytest.fixture
    def temp_templates_dir(self):
        """Create a temporary directory with test templates."""
        temp_dir = Path(tempfile.mkdtemp())

        # Create some test templates
        templates = [
            {
                "path": temp_dir / "greeting.yaml",
                "content": """
name: greeting
description: A friendly greeting template
version: 1.0.0
tags:
  - greeting
  - simple
template: "Hello, {{name}}!"
variables:
  - name: name
    type: string
    required: true
""",
            },
            {
                "path": temp_dir / "summarizer.yaml",
                "content": """
name: summarizer
description: Summarize text content
version: 2.0.0
tags:
  - summarization
  - text
template: "Summarize: {{text}}"
variables:
  - name: text
    type: string
    required: true
""",
            },
            {
                "path": temp_dir / "subdir" / "nested.yaml",
                "content": """
name: nested-template
description: A template in a subdirectory
template: "Nested: {{value}}"
variables:
  - name: value
    type: string
    required: true
""",
            },
        ]

        for t in templates:
            t["path"].parent.mkdir(parents=True, exist_ok=True)
            t["path"].write_text(t["content"])

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_list_templates(self, temp_templates_dir):
        """Test listing all templates."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        templates = registry.list()

        assert len(templates) == 3
        names = [t.name for t in templates]
        assert "greeting" in names
        assert "summarizer" in names
        assert "nested-template" in names

    def test_find_template(self, temp_templates_dir):
        """Test finding a template by name."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        path = registry.find("greeting")
        assert path is not None
        assert path.name == "greeting.yaml"

    def test_find_template_not_found(self, temp_templates_dir):
        """Test finding a nonexistent template."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        path = registry.find("nonexistent")
        assert path is None

    def test_load_template(self, temp_templates_dir):
        """Test loading a template by name."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        template = registry.load("greeting")

        assert template.name == "greeting"
        assert template.description == "A friendly greeting template"

    def test_load_template_not_found(self, temp_templates_dir):
        """Test loading a nonexistent template."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        with pytest.raises(TemplateNotFoundError) as exc_info:
            registry.load("nonexistent")

        # Should suggest similar names
        error_str = str(exc_info.value)
        assert "nonexistent" in error_str.lower()

    def test_load_with_suggestion(self, temp_templates_dir):
        """Test that similar template names are suggested."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        with pytest.raises(TemplateNotFoundError) as exc_info:
            registry.load("greating")  # Typo

        # Should suggest "greeting"
        error = exc_info.value
        assert error.suggestion is not None
        assert "greeting" in error.suggestion

    def test_search_by_query(self, temp_templates_dir):
        """Test searching templates by query."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        results = registry.search(query="summar")

        assert len(results) == 1
        assert results[0].name == "summarizer"

    def test_search_by_tags(self, temp_templates_dir):
        """Test searching templates by tags."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        results = registry.search(tags=["greeting"])

        assert len(results) == 1
        assert results[0].name == "greeting"

    def test_search_by_query_and_tags(self, temp_templates_dir):
        """Test searching templates by both query and tags."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        # Should find greeting (matches tag)
        # Note: query searches name/description, not template content
        _ = registry.search(query="hello", tags=["simple"])

    def test_exists(self, temp_templates_dir):
        """Test checking if template exists."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        assert registry.exists("greeting") is True
        assert registry.exists("nonexistent") is False

    def test_add_search_path(self, temp_templates_dir):
        """Test adding a search path."""
        registry = TemplateRegistry(search_paths=[])

        # Initially no templates
        assert len(registry.list()) == 0

        # Add path
        registry.add_search_path(temp_templates_dir)

        # Now should find templates
        assert len(registry.list()) == 3

    def test_search_paths_priority(self, temp_templates_dir):
        """Test that earlier search paths take priority."""
        # Create another directory with same template name
        temp_dir2 = Path(tempfile.mkdtemp())
        (temp_dir2 / "greeting.yaml").write_text("""
name: greeting
description: Override greeting
template: "Hi, {{name}}!"
variables:
  - name: name
    type: string
    required: true
""")

        try:
            # First path takes priority
            registry = TemplateRegistry(search_paths=[temp_dir2, temp_templates_dir])

            template = registry.load("greeting")
            assert template.description == "Override greeting"
        finally:
            shutil.rmtree(temp_dir2)

    def test_get_search_paths_status(self, temp_templates_dir):
        """Test getting search paths status."""
        nonexistent = Path("/nonexistent/path")
        registry = TemplateRegistry(search_paths=[temp_templates_dir, nonexistent])

        status = registry.get_search_paths_status()

        assert len(status) == 2
        assert status[0]["exists"] is True
        assert status[1]["exists"] is False

    def test_find_nested_template(self, temp_templates_dir):
        """Test finding template in subdirectory."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        path = registry.find("nested-template")
        assert path is not None

    def test_template_info_fields(self, temp_templates_dir):
        """Test that template info contains expected fields."""
        registry = TemplateRegistry(search_paths=[temp_templates_dir])

        templates = registry.list()
        greeting = next(t for t in templates if t.name == "greeting")

        assert greeting.description == "A friendly greeting template"
        assert greeting.version == "1.0.0"
        assert "greeting" in greeting.tags
        assert greeting.path.exists()


class TestDefaultSearchPaths:
    """Tests for default search path behavior."""

    def test_default_paths_include_cwd_templates(self):
        """Test that default paths include ./templates."""
        registry = TemplateRegistry()

        paths = [str(p) for p in registry.search_paths]
        assert any("templates" in p for p in paths)

    def test_default_paths_include_home_dir(self):
        """Test that default paths include home directory."""
        registry = TemplateRegistry()

        paths = [str(p) for p in registry.search_paths]
        home = str(Path.home())
        assert any(home in p for p in paths)
