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
    load_repomap_to_context,
    SOURCE_CODE_EXTENSIONS,
    REPOMAP_EXCLUDE_DIRS,
    REPOMAP_EXCLUDE_SUFFIXES,
    MAX_FILE_CONTENT_PREVIEW,
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
            # Use os.path.join for cross-platform compatibility
            expected_nested_path = os.path.join('src', 'utils', 'helper.py')
            assert expected_nested_path in paths

    def test_includes_file_size(self):
        """Test that file size is included in result and is accurate byte size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content = "print('hello world')"
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(content)
            
            files = collect_source_files(tmpdir)
            
            # Verify size key exists and is a positive integer
            assert 'size' in files[0]
            assert isinstance(files[0]['size'], int)
            assert files[0]['size'] > 0
            # Verify it matches actual file size (byte size)
            assert files[0]['size'] == test_file.stat().st_size


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
        
        # Content should be truncated to approximately MAX_FILE_CONTENT_PREVIEW chars
        # The prompt should not contain all 5000 chars
        # Allow some overhead for markdown formatting (code block markers etc)
        x_count = prompt.count('x')
        assert x_count <= MAX_FILE_CONTENT_PREVIEW + 100  # Allow small overhead for formatting

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

    def test_includes_tree_when_provided(self):
        """Test that tree output is included when provided."""
        files = [{'path': 'test.py', 'content': 'print("hello")', 'size': 15}]
        tree_output = """project/
├── src/
│   └── main.py
└── README.md"""
        
        prompt = generate_repomap_prompt(files, tree_output=tree_output)
        
        # Check that tree is included
        assert 'Directory Tree' in prompt
        assert 'src/' in prompt
        assert 'main.py' in prompt
        assert 'README.md' in prompt

    def test_no_tree_section_when_not_provided(self):
        """Test that tree section is not included when tree_output is None."""
        files = [{'path': 'test.py', 'content': 'print("hello")', 'size': 15}]
        
        prompt = generate_repomap_prompt(files, tree_output=None)
        
        # When tree_output is None, the "Directory Tree" section should not appear
        # The prompt should still have "Directory Structure" in the instructions section
        # but not the actual tree content section header
        assert '## Directory Tree' not in prompt


class TestMaxFileContentPreview:
    """Tests for MAX_FILE_CONTENT_PREVIEW constant."""

    def test_constant_value(self):
        """Test that the constant has an appropriate value."""
        assert MAX_FILE_CONTENT_PREVIEW == 2000
        assert isinstance(MAX_FILE_CONTENT_PREVIEW, int)


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


class TestRepomapExcludeSuffixes:
    """Tests for REPOMAP_EXCLUDE_SUFFIXES constant and suffix-based exclusion."""

    def test_egg_info_suffix_exists(self):
        """Test that .egg-info suffix pattern is defined."""
        assert '.egg-info' in REPOMAP_EXCLUDE_SUFFIXES

    def test_excludes_egg_info_directories(self):
        """Test that directories ending with .egg-info are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file in an egg-info directory
            egg_dir = Path(tmpdir) / "mypackage.egg-info"
            egg_dir.mkdir(parents=True)
            (egg_dir / "PKG-INFO").write_text("Package info")
            (egg_dir / "SOURCES.txt").write_text("sources")
            
            # Create a regular file that should be included
            (Path(tmpdir) / "setup.py").write_text("# Setup file")
            
            files = collect_source_files(tmpdir)
            
            # Should only include setup.py, not files from .egg-info
            assert len(files) == 1
            assert files[0]['path'] == 'setup.py'


class TestLoadRepomapToContext:
    """Tests for load_repomap_to_context async function."""

    @pytest.mark.asyncio
    async def test_returns_error_on_empty_result(self):
        """Test that empty result returns proper error dict."""
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                return None
        
        result = await load_repomap_to_context(MockMCPClient(), '/path/to/.repomap', '/path')
        
        assert result['status'] == 'error'
        assert 'empty result' in result['message'].lower()

    @pytest.mark.asyncio
    async def test_returns_parsed_json_on_success(self):
        """Test that valid JSON response is parsed correctly."""
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                return '{"status": "success", "message": "Loaded"}'
        
        result = await load_repomap_to_context(MockMCPClient(), '/path/to/.repomap', '/path')
        
        assert result['status'] == 'success'
        assert result['message'] == 'Loaded'

    @pytest.mark.asyncio
    async def test_handles_json_decode_error(self):
        """Test that invalid JSON returns proper error dict."""
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                return 'not valid json {'
        
        result = await load_repomap_to_context(MockMCPClient(), '/path/to/.repomap', '/path')
        
        assert result['status'] == 'error'
        assert 'Failed to parse' in result['message']

    @pytest.mark.asyncio
    async def test_handles_long_error_response_truncation(self):
        """Test that long error responses are truncated in error message."""
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                return 'x' * 200  # Long non-JSON string
        
        result = await load_repomap_to_context(MockMCPClient(), '/path/to/.repomap', '/path')
        
        assert result['status'] == 'error'
        # Should be truncated with ...
        assert '...' in result['message']
        # Should not contain full 200 chars
        assert 'x' * 200 not in result['message']

    @pytest.mark.asyncio
    async def test_passes_session_id_when_provided(self):
        """Test that session_id is passed to MCP client when provided."""
        captured_args = {}
        
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                captured_args.update(args)
                return '{"status": "success"}'
        
        await load_repomap_to_context(
            MockMCPClient(), 
            '/path/to/.repomap', 
            '/path',
            session_id='test-session-123'
        )
        
        assert captured_args.get('session_id') == 'test-session-123'

    @pytest.mark.asyncio
    async def test_omits_session_id_when_not_provided(self):
        """Test that session_id is not passed when None."""
        captured_args = {}
        
        class MockMCPClient:
            async def call_tool(self, server, tool, args):
                captured_args.update(args)
                return '{"status": "success"}'
        
        await load_repomap_to_context(MockMCPClient(), '/path/to/.repomap', '/path')
        
        assert 'session_id' not in captured_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
