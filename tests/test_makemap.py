"""Tests for the makemap functionality."""

import pytest
import tempfile
import os
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.makemap import (
    find_makefile,
    parse_makefile,
    collect_makefile_targets,
    generate_makemap_prompt,
    generate_makemap_update_prompt,
    get_target_names,
    find_target_by_name,
    validate_target,
)


@pytest.mark.unit
class TestFindMakefile:
    """Tests for find_makefile function."""

    def test_finds_makefile(self):
        """Test that Makefile is found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("all:\n\techo hello")

            result = find_makefile(tmpdir)

            assert result is not None
            assert result.name == "Makefile"

    def test_finds_lowercase_makefile(self):
        """Test that lowercase makefile is found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "makefile"
            makefile.write_text("all:\n\techo hello")

            result = find_makefile(tmpdir)

            assert result is not None
            assert result.name == "makefile"

    def test_finds_gnumakefile(self):
        """Test that GNUmakefile is found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "GNUmakefile"
            makefile.write_text("all:\n\techo hello")

            result = find_makefile(tmpdir)

            assert result is not None
            assert result.name == "GNUmakefile"

    def test_prefers_makefile_over_lowercase(self):
        """Test that Makefile is preferred over makefile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Makefile").write_text("# Uppercase")
            (Path(tmpdir) / "makefile").write_text("# Lowercase")

            result = find_makefile(tmpdir)

            assert result is not None
            assert result.name == "Makefile"

    def test_returns_none_when_no_makefile(self):
        """Test that None is returned when no Makefile exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_makefile(tmpdir)
            assert result is None


@pytest.mark.unit
class TestParseMakefile:
    """Tests for parse_makefile function."""

    def test_parses_simple_target(self):
        """Test parsing a simple target."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("""
all:
\techo "Building all"
""")

            result = parse_makefile(str(makefile))

            assert 'error' not in result
            assert len(result['targets']) == 1
            assert result['targets'][0]['name'] == 'all'

    def test_parses_target_with_dependencies(self):
        """Test parsing a target with dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("""
build: clean install
\techo "Building"

clean:
\trm -rf dist

install:
\tpip install -r requirements.txt
""")

            result = parse_makefile(str(makefile))

            assert 'error' not in result
            build_target = next(t for t in result['targets'] if t['name'] == 'build')
            assert 'clean' in build_target['dependencies']
            assert 'install' in build_target['dependencies']

    def test_parses_target_with_description(self):
        """Test parsing a target with ## description comment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("""
test: ## Run the tests
\tpytest
""")

            result = parse_makefile(str(makefile))

            assert 'error' not in result
            test_target = result['targets'][0]
            assert test_target['name'] == 'test'
            assert test_target['description'] == 'Run the tests'

    def test_parses_variables(self):
        """Test parsing variable definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("""
PYTHON := python3
VENV := venv

all:
\techo "done"
""")

            result = parse_makefile(str(makefile))

            assert 'error' not in result
            assert 'PYTHON' in result['variables']
            assert result['variables']['PYTHON']['value'] == 'python3'
            assert 'VENV' in result['variables']
            assert result['variables']['VENV']['value'] == 'venv'

    def test_parses_phony_targets(self):
        """Test parsing .PHONY declarations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("""
.PHONY: all clean test

all:
\techo "all"

clean:
\trm -rf dist
""")

            result = parse_makefile(str(makefile))

            assert 'error' not in result
            assert 'all' in result['phony_targets']
            assert 'clean' in result['phony_targets']
            assert 'test' in result['phony_targets']

    def test_extracts_recipe(self):
        """Test that recipe lines are extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("""
build:
\techo "Step 1"
\techo "Step 2"
\techo "Step 3"
""")

            result = parse_makefile(str(makefile))

            assert 'error' not in result
            build_target = result['targets'][0]
            assert 'Step 1' in build_target['recipe']
            assert 'Step 2' in build_target['recipe']

    def test_returns_error_for_nonexistent_file(self):
        """Test that error is returned for nonexistent file."""
        result = parse_makefile('/nonexistent/path/Makefile')

        assert 'error' in result
        assert 'not found' in result['error']


@pytest.mark.unit
class TestCollectMakefileTargets:
    """Tests for collect_makefile_targets function."""

    def test_collects_targets_from_working_dir(self):
        """Test collecting targets from a working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            makefile = Path(tmpdir) / "Makefile"
            makefile.write_text("""
all: build test

build:
\techo "Building"

test:
\tpytest
""")

            result = collect_makefile_targets(tmpdir)

            assert result['found'] is True
            assert len(result['targets']) == 3

    def test_returns_not_found_when_no_makefile(self):
        """Test that found=False when no Makefile exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = collect_makefile_targets(tmpdir)

            assert result['found'] is False
            assert 'error' in result


@pytest.mark.unit
class TestGenerateMakemapPrompt:
    """Tests for generate_makemap_prompt function."""

    def test_generates_prompt_with_targets(self):
        """Test that prompt includes target information."""
        parsed = {
            'targets': [
                {'name': 'build', 'dependencies': ['clean'], 'description': 'Build project', 'recipe': 'make clean'},
                {'name': 'test', 'dependencies': [], 'description': 'Run tests', 'recipe': 'pytest'},
            ],
            'variables': {'PYTHON': {'value': 'python3', 'description': None}},
            'content': 'build: clean\n\tmake clean\n\ntest:\n\tpytest'
        }

        prompt = generate_makemap_prompt(parsed)

        assert 'build' in prompt
        assert 'test' in prompt
        assert 'PYTHON' in prompt

    def test_generates_prompt_with_tree(self):
        """Test that prompt includes tree output when provided."""
        parsed = {
            'targets': [],
            'variables': {},
            'content': ''
        }

        prompt = generate_makemap_prompt(parsed, tree_output=".\n├── src\n└── tests")

        assert 'Directory Tree' in prompt
        assert 'src' in prompt
        assert 'tests' in prompt


@pytest.mark.unit
class TestGenerateMakemapUpdatePrompt:
    """Tests for generate_makemap_update_prompt function."""

    def test_generates_update_prompt(self):
        """Test that update prompt includes new targets."""
        new_targets = [
            {'name': 'deploy', 'dependencies': ['build'], 'description': 'Deploy to prod', 'recipe': 'deploy.sh'},
        ]
        existing_makemap = "# Existing content\n## Targets\n### build\n..."

        prompt = generate_makemap_update_prompt(new_targets, existing_makemap)

        assert 'deploy' in prompt
        assert 'NEW' in prompt.upper()
        assert 'Existing content' in prompt


@pytest.mark.unit
class TestGetTargetNames:
    """Tests for get_target_names function."""

    def test_extracts_target_names(self):
        """Test extracting just target names."""
        parsed = {
            'targets': [
                {'name': 'all', 'dependencies': []},
                {'name': 'build', 'dependencies': []},
                {'name': 'test', 'dependencies': []},
            ]
        }

        names = get_target_names(parsed)

        assert names == ['all', 'build', 'test']

    def test_returns_empty_for_no_targets(self):
        """Test returning empty list when no targets."""
        parsed = {'targets': []}
        names = get_target_names(parsed)
        assert names == []


@pytest.mark.unit
class TestFindTargetByName:
    """Tests for find_target_by_name function."""

    def test_finds_existing_target(self):
        """Test finding an existing target."""
        parsed = {
            'targets': [
                {'name': 'build', 'dependencies': ['clean']},
                {'name': 'test', 'dependencies': []},
            ]
        }

        target = find_target_by_name(parsed, 'build')

        assert target is not None
        assert target['name'] == 'build'
        assert 'clean' in target['dependencies']

    def test_returns_none_for_nonexistent_target(self):
        """Test returning None for nonexistent target."""
        parsed = {
            'targets': [
                {'name': 'build', 'dependencies': []},
            ]
        }

        target = find_target_by_name(parsed, 'nonexistent')

        assert target is None


@pytest.mark.unit
class TestValidateTarget:
    """Tests for validate_target function."""

    def test_validates_existing_target(self):
        """Test validating an existing target."""
        parsed = {
            'targets': [
                {'name': 'build', 'dependencies': []},
            ]
        }

        assert validate_target(parsed, 'build') is True

    def test_invalidates_nonexistent_target(self):
        """Test invalidating a nonexistent target."""
        parsed = {
            'targets': [
                {'name': 'build', 'dependencies': []},
            ]
        }

        assert validate_target(parsed, 'nonexistent') is False


@pytest.mark.unit
class TestRealMakefile:
    """Tests using the actual project Makefile."""

    def test_parses_project_makefile(self):
        """Test parsing the project's actual Makefile."""
        project_root = Path(__file__).parent.parent
        makefile_path = project_root / "Makefile"

        if not makefile_path.exists():
            pytest.skip("Project Makefile not found")

        result = parse_makefile(str(makefile_path))

        assert 'error' not in result
        # The project Makefile should have many targets
        assert len(result['targets']) > 10

        # Check for known targets
        target_names = [t['name'] for t in result['targets']]
        assert 'test' in target_names
        assert 'build' in target_names or 'setup' in target_names
