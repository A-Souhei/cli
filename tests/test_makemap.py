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

from src.cli.commands.make import sanitize_make_command


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

        # Check that prompt contains the Makefile content with target names
        assert 'build' in prompt
        assert 'test' in prompt
        # Check that the prompt instructs to create makemap format
        assert 'Make Commands' in prompt
        assert 'markdown table' in prompt.lower() or 'Table Format' in prompt

    def test_generates_prompt_with_tree(self):
        """Test that tree_output is accepted for API compatibility (but not used in new format)."""
        parsed = {
            'targets': [],
            'variables': {},
            'content': ''
        }

        # tree_output is kept for API compatibility but no longer used in the prompt
        prompt = generate_makemap_prompt(parsed, tree_output=".\n├── src\n└── tests")

        # The new format doesn't include directory tree, but should still generate a valid prompt
        assert 'Make Commands' in prompt
        assert 'Instructions' in prompt


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


@pytest.mark.unit
class TestSanitizeMakeCommand:
    """Tests for sanitize_make_command function to prevent command injection."""

    def test_valid_simple_command(self):
        """Test that simple make commands are valid."""
        is_valid, cmd_list, error = sanitize_make_command("make test")
        assert is_valid
        assert cmd_list == ["make", "test"]
        assert error == ""

    def test_valid_command_with_multiple_targets(self):
        """Test make command with multiple targets."""
        is_valid, cmd_list, error = sanitize_make_command("make clean build")
        assert is_valid
        assert cmd_list == ["make", "clean", "build"]
        assert error == ""

    def test_valid_command_with_flags(self):
        """Test make command with flags."""
        is_valid, cmd_list, error = sanitize_make_command("make -j4 test")
        assert is_valid
        assert cmd_list == ["make", "-j4", "test"]
        assert error == ""

        is_valid, cmd_list, error = sanitize_make_command("make --dry-run test")
        assert is_valid
        assert cmd_list == ["make", "--dry-run", "test"]
        assert error == ""

    def test_valid_command_with_variable_assignment(self):
        """Test make command with variable assignments."""
        is_valid, cmd_list, error = sanitize_make_command("make VAR=value test")
        assert is_valid
        assert cmd_list == ["make", "VAR=value", "test"]
        assert error == ""

    def test_valid_command_with_path_target(self):
        """Test make command with path-like target."""
        is_valid, cmd_list, error = sanitize_make_command("make src/utils/build")
        assert is_valid
        assert cmd_list == ["make", "src/utils/build"]
        assert error == ""

    def test_invalid_empty_command(self):
        """Test that empty commands are rejected."""
        is_valid, cmd_list, error = sanitize_make_command("")
        assert not is_valid
        assert cmd_list == []
        assert "Empty" in error

    def test_invalid_non_make_command(self):
        """Test that non-make commands are rejected."""
        is_valid, cmd_list, error = sanitize_make_command("rm -rf /")
        assert not is_valid
        assert cmd_list == []
        assert "make" in error.lower()

    def test_invalid_command_injection_semicolon(self):
        """Test that semicolon command injection is rejected."""
        is_valid, cmd_list, error = sanitize_make_command("make test; rm -rf /")
        assert not is_valid
        assert cmd_list == []

    def test_invalid_command_injection_pipe(self):
        """Test that pipe command injection is rejected."""
        is_valid, cmd_list, error = sanitize_make_command("make test | cat /etc/passwd")
        assert not is_valid
        assert cmd_list == []

    def test_invalid_command_injection_ampersand(self):
        """Test that ampersand command injection is rejected."""
        is_valid, cmd_list, error = sanitize_make_command("make test && rm -rf /")
        assert not is_valid
        assert cmd_list == []

    def test_invalid_command_injection_backtick(self):
        """Test that backtick command injection is rejected."""
        is_valid, cmd_list, error = sanitize_make_command("make VAR=`whoami` test")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_invalid_command_injection_dollar(self):
        """Test that dollar sign command injection is rejected."""
        is_valid, cmd_list, error = sanitize_make_command("make VAR=$(whoami) test")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_invalid_command_injection_redirect(self):
        """Test that redirect injection is rejected."""
        is_valid, cmd_list, error = sanitize_make_command("make VAR=>malicious test")
        assert not is_valid

    def test_valid_make_only(self):
        """Test that bare 'make' command is valid."""
        is_valid, cmd_list, error = sanitize_make_command("make")
        assert is_valid
        assert cmd_list == ["make"]
        assert error == ""

    def test_valid_target_with_dots(self):
        """Test target with dots is valid."""
        is_valid, cmd_list, error = sanitize_make_command("make file.o")
        assert is_valid
        assert cmd_list == ["make", "file.o"]

    def test_valid_target_with_dashes(self):
        """Test target with dashes is valid."""
        is_valid, cmd_list, error = sanitize_make_command("make run-tests")
        assert is_valid
        assert cmd_list == ["make", "run-tests"]

    def test_valid_target_with_underscores(self):
        """Test target with underscores is valid."""
        is_valid, cmd_list, error = sanitize_make_command("make run_tests")
        assert is_valid
        assert cmd_list == ["make", "run_tests"]
