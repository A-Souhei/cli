"""Tests for the repomap functionality."""

import pytest
import tempfile
import os
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import (
    collect_source_files,
    generate_repomap_prompt,
    SOURCE_CODE_EXTENSIONS,
    REPOMAP_EXCLUDE_DIRS,
)


class TestCollectSourceFiles:
    """Tests for collect_source_files function."""

    def test_collects_python_files(self):
        """Test that Python files are collected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Python file
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("print('hello')")
            
            files = collect_source_files(tmpdir)
            
            assert len(files) == 1
            assert files[0]['path'] == 'test.py'
            assert "print('hello')" in files[0]['content']

    def test_collects_multiple_file_types(self):
        """Test that multiple source file types are collected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create various source files
            (Path(tmpdir) / "app.py").write_text("# Python")
            (Path(tmpdir) / "script.js").write_text("// JavaScript")
            (Path(tmpdir) / "config.yaml").write_text("key: value")
            (Path(tmpdir) / "README.md").write_text("# Readme")
            
            files = collect_source_files(tmpdir)
            
            assert len(files) == 4
            paths = [f['path'] for f in files]
            assert 'app.py' in paths
            assert 'script.js' in paths
            assert 'config.yaml' in paths
            assert 'README.md' in paths

    def test_excludes_venv_directory(self):
        """Test that venv directory is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file in venv
            venv_dir = Path(tmpdir) / "venv" / "lib"
            venv_dir.mkdir(parents=True)
            (venv_dir / "test.py").write_text("# Should be excluded")
            
            # Create a file outside venv
            (Path(tmpdir) / "app.py").write_text("# Should be included")
            
            files = collect_source_files(tmpdir)
            
            assert len(files) == 1
            assert files[0]['path'] == 'app.py'

    def test_excludes_node_modules(self):
        """Test that node_modules directory is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file in node_modules
            node_dir = Path(tmpdir) / "node_modules" / "package"
            node_dir.mkdir(parents=True)
            (node_dir / "index.js").write_text("// Should be excluded")
            
            # Create a file outside node_modules
            (Path(tmpdir) / "app.js").write_text("// Should be included")
            
            files = collect_source_files(tmpdir)
            
            assert len(files) == 1
            assert files[0]['path'] == 'app.js'

    def test_excludes_git_directory(self):
        """Test that .git directory is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files in .git
            git_dir = Path(tmpdir) / ".git" / "objects"
            git_dir.mkdir(parents=True)
            (git_dir / "test").write_text("git object")
            
            # Create a regular file
            (Path(tmpdir) / "main.py").write_text("# Main file")
            
            files = collect_source_files(tmpdir)
            
            assert len(files) == 1
            assert files[0]['path'] == 'main.py'

    def test_respects_max_files_limit(self):
        """Test that max_files limit is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files
            for i in range(20):
                (Path(tmpdir) / f"file{i}.py").write_text(f"# File {i}")
            
            files = collect_source_files(tmpdir, max_files=5)
            
            assert len(files) == 5

    def test_handles_empty_directory(self):
        """Test handling of empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = collect_source_files(tmpdir)
            
            assert len(files) == 0

    def test_handles_nested_directories(self):
        """Test collection from nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            nested = Path(tmpdir) / "src" / "utils"
            nested.mkdir(parents=True)
            (nested / "helper.py").write_text("# Helper")
            (Path(tmpdir) / "main.py").write_text("# Main")
            
            files = collect_source_files(tmpdir)
            
            assert len(files) == 2
            paths = [f['path'] for f in files]
            assert 'main.py' in paths
            assert 'src/utils/helper.py' in paths or 'src\\utils\\helper.py' in paths

    def test_includes_file_size(self):
        """Test that file size is included in result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content = "print('hello world')"
            (Path(tmpdir) / "test.py").write_text(content)
            
            files = collect_source_files(tmpdir)
            
            assert files[0]['size'] == len(content)


class TestGenerateRepomapPrompt:
    """Tests for generate_repomap_prompt function."""

    def test_generates_prompt_with_files(self):
        """Test that prompt is generated with file information."""
        files = [
            {'path': 'main.py', 'content': 'print("hello")', 'size': 15},
            {'path': 'utils.py', 'content': 'def helper(): pass', 'size': 19},
        ]
        
        prompt = generate_repomap_prompt(files)
        
        # Check that file paths are included
        assert 'main.py' in prompt
        assert 'utils.py' in prompt
        
        # Check that content is included
        assert 'print("hello")' in prompt
        assert 'def helper()' in prompt

    def test_includes_instruction_sections(self):
        """Test that prompt includes all required instruction sections."""
        files = [{'path': 'test.py', 'content': '# test', 'size': 6}]
        
        prompt = generate_repomap_prompt(files)
        
        # Check for key sections
        assert 'Project Overview' in prompt
        assert 'Architecture' in prompt
        assert 'Directory Structure' in prompt
        assert 'Key Components' in prompt
        assert 'Entry Points' in prompt
        assert 'Dependencies' in prompt
        assert 'Data Flow' in prompt
        assert 'Configuration' in prompt
        assert 'Testing' in prompt
        assert 'Getting Started' in prompt

    def test_truncates_long_content(self):
        """Test that very long file content is truncated."""
        long_content = "x" * 5000  # 5000 chars
        files = [{'path': 'big.py', 'content': long_content, 'size': 5000}]
        
        prompt = generate_repomap_prompt(files)
        
        # Content should be truncated to approximately 2000 chars
        # The prompt should not contain all 5000 chars
        # Allow some overhead for markdown formatting (code block markers etc)
        x_count = prompt.count('x')
        assert x_count <= 2100  # Allow small overhead for formatting

    def test_handles_empty_files_list(self):
        """Test handling of empty files list."""
        files = []
        
        prompt = generate_repomap_prompt(files)
        
        # Should still generate a valid prompt structure
        assert 'Project Overview' in prompt
        assert 'repository map' in prompt.lower()

    def test_includes_file_size_info(self):
        """Test that file size information is included."""
        files = [{'path': 'test.py', 'content': 'code', 'size': 100}]
        
        prompt = generate_repomap_prompt(files)
        
        assert '100 bytes' in prompt or '100' in prompt


class TestSourceCodeExtensions:
    """Tests for SOURCE_CODE_EXTENSIONS constant."""

    def test_includes_common_extensions(self):
        """Test that common source file extensions are included."""
        expected = ['.py', '.js', '.ts', '.java', '.go', '.rs', '.rb', '.php']
        
        for ext in expected:
            assert ext in SOURCE_CODE_EXTENSIONS, f"Missing extension: {ext}"

    def test_includes_config_extensions(self):
        """Test that config file extensions are included."""
        expected = ['.json', '.yaml', '.yml', '.toml']
        
        for ext in expected:
            assert ext in SOURCE_CODE_EXTENSIONS, f"Missing extension: {ext}"


class TestRepomapExcludeDirs:
    """Tests for REPOMAP_EXCLUDE_DIRS constant."""

    def test_includes_common_excludes(self):
        """Test that common directories to exclude are included."""
        expected = [
            '.git', '__pycache__', 'node_modules', 
            'venv', '.venv', 'dist', 'build'
        ]
        
        for dirname in expected:
            assert dirname in REPOMAP_EXCLUDE_DIRS, f"Missing exclude dir: {dirname}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
