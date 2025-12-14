"""Template registry for discovering and loading templates."""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path

from .template import Template, TemplateNotFoundError


@dataclass
class TemplateInfo:
    """Information about a discovered template."""

    name: str
    path: Path
    description: str = ""
    version: str = ""
    tags: list[str] = field(default_factory=list)


class TemplateRegistry:
    """Registry for discovering and loading templates from multiple sources."""

    SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}

    def __init__(self, search_paths: list[Path] | None = None) -> None:
        """Initialize the registry.

        Args:
            search_paths: List of directories to search for templates.
                         If None, uses default paths.
        """
        if search_paths is None:
            search_paths = self._default_search_paths()

        self.search_paths = [Path(p) for p in search_paths]

    @staticmethod
    def _default_search_paths() -> list[Path]:
        """Get default search paths for templates.

        Returns:
            List of default paths to search
        """
        paths = [
            Path.cwd() / "templates",
            Path.cwd() / "prompts",
            Path.home() / ".prompt_templates",
        ]
        return paths

    def add_search_path(self, path: Path | str) -> None:
        """Add a search path to the registry.

        Args:
            path: Directory path to add
        """
        path = Path(path)
        if path not in self.search_paths:
            self.search_paths.insert(0, path)

    def find(self, name: str) -> Path | None:
        """Find a template file by name.

        Searches by both file name and template name (the 'name' field inside the YAML).

        Args:
            name: Template name (with or without extension)

        Returns:
            Path to the template file, or None if not found
        """
        # If name includes extension, search as-is
        name_path = Path(name)
        if name_path.suffix in self.SUPPORTED_EXTENSIONS:
            for base_path in self.search_paths:
                candidate = base_path / name
                if candidate.exists():
                    return candidate
            return None

        # Search with each supported extension (by file name)
        for base_path in self.search_paths:
            if not base_path.exists():
                continue

            for ext in self.SUPPORTED_EXTENSIONS:
                candidate = base_path / f"{name}{ext}"
                if candidate.exists():
                    return candidate

                # Also check subdirectories
                for subdir in base_path.iterdir():
                    if subdir.is_dir():
                        candidate = subdir / f"{name}{ext}"
                        if candidate.exists():
                            return candidate

        # If not found by file name, search by template name (inside YAML)
        for info in self._discover_templates():
            if info.name == name:
                return info.path

        return None

    def load(self, name: str) -> Template:
        """Load a template by name.

        Args:
            name: Template name

        Returns:
            Template instance

        Raises:
            TemplateNotFoundError: If template not found
        """
        path = self.find(name)

        if path is None:
            # Get suggestions for similar names
            available = [t.name for t in self.list()]
            suggestions = get_close_matches(name, available, n=3, cutoff=0.4)

            suggestion_text = None
            if suggestions:
                suggestion_text = f"Did you mean: {', '.join(suggestions)}?"

            raise TemplateNotFoundError(
                f"Template '{name}' not found",
                suggestion=suggestion_text,
                context={
                    "search_paths": [str(p) for p in self.search_paths if p.exists()]
                },
            )

        return Template.from_file(path)

    def list(self) -> builtins.list[TemplateInfo]:
        """List all available templates.

        Returns:
            List of TemplateInfo for all discovered templates
        """
        templates = []
        seen_names: set[str] = set()

        for info in self._discover_templates():
            # Skip duplicates (first found wins)
            if info.name in seen_names:
                continue
            seen_names.add(info.name)
            templates.append(info)

        # Sort by name
        templates.sort(key=lambda t: t.name)
        return templates

    def _discover_templates(self) -> Iterator[TemplateInfo]:
        """Discover all templates in search paths.

        Yields:
            TemplateInfo for each discovered template
        """
        for base_path in self.search_paths:
            if not base_path.exists():
                continue

            yield from self._scan_directory(base_path)

    def _scan_directory(self, directory: Path) -> Iterator[TemplateInfo]:
        """Scan a directory for template files.

        Args:
            directory: Directory to scan

        Yields:
            TemplateInfo for each template found
        """
        try:
            for item in directory.iterdir():
                if item.is_file() and item.suffix in self.SUPPORTED_EXTENSIONS:
                    info = self._get_template_info(item)
                    if info:
                        yield info
                elif item.is_dir() and not item.name.startswith("."):
                    # Recursively scan subdirectories
                    yield from self._scan_directory(item)
        except PermissionError:
            pass  # Skip directories we can't read

    def _get_template_info(self, path: Path) -> TemplateInfo | None:
        """Extract template info from a file.

        Args:
            path: Path to template file

        Returns:
            TemplateInfo or None if file is invalid
        """
        try:
            template = Template.from_file(path)
            return TemplateInfo(
                name=template.name,
                path=path,
                description=template.description,
                version=template.config.version,
                tags=template.config.tags,
            )
        except Exception:
            # Skip invalid template files
            return None

    def search(
        self,
        query: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> builtins.list[TemplateInfo]:
        """Search for templates by name/description or tags.

        Args:
            query: Search query for name/description
            tags: Filter by tags (any match)

        Returns:
            List of matching templates
        """
        templates = self.list()

        if query:
            query_lower = query.lower()
            templates = [
                t
                for t in templates
                if query_lower in t.name.lower()
                or query_lower in t.description.lower()
            ]

        if tags:
            tags_set = set(tag.lower() for tag in tags)
            templates = [
                t
                for t in templates
                if any(tag.lower() in tags_set for tag in t.tags)
            ]

        return templates

    def exists(self, name: str) -> bool:
        """Check if a template exists.

        Args:
            name: Template name

        Returns:
            True if template exists
        """
        return self.find(name) is not None

    def get_search_paths_status(self) -> builtins.list[dict[str, str | bool]]:
        """Get status of all search paths.

        Returns:
            List of dicts with path and exists status
        """
        return [
            {"path": str(p), "exists": p.exists()}
            for p in self.search_paths
        ]
