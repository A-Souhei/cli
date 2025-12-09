"""Tests for .llmignore functionality."""

import os
import tempfile
import shutil

from src.utils.llmignore import (
    LLMIgnorePattern,
    LLMIgnore,
    get_llmignore,
    is_file_ignored,
    filter_at_context
)


class TestLLMIgnorePattern:
    """Test individual pattern matching."""
    
    def test_simple_filename_pattern(self):
        """Test simple filename pattern like *.env"""
        pattern = LLMIgnorePattern("*.env")
        assert pattern.matches(".env")
        assert pattern.matches("test.env")
        assert pattern.matches("dir/test.env")
        assert not pattern.matches("env.txt")
    
    def test_directory_pattern(self):
        """Test directory pattern like secrets/"""
        pattern = LLMIgnorePattern("secrets/")
        assert pattern.matches("secrets", is_dir=True)
        assert pattern.matches("dir/secrets", is_dir=True)
        assert not pattern.matches("secrets", is_dir=False)
        assert not pattern.matches("secrets.txt", is_dir=True)
    
    def test_anchored_pattern(self):
        """Test anchored pattern like /config.yaml"""
        pattern = LLMIgnorePattern("/config.yaml")
        assert pattern.matches("config.yaml")
        assert not pattern.matches("dir/config.yaml")
    
    def test_negation_pattern(self):
        """Test negation pattern like !important.env"""
        pattern = LLMIgnorePattern("!important.env", is_negation=True)
        assert pattern.is_negation
        assert pattern.matches("important.env")
    
    def test_wildcard_pattern(self):
        """Test wildcard patterns"""
        pattern = LLMIgnorePattern("*.log")
        assert pattern.matches("app.log")
        assert pattern.matches("test/debug.log")
        assert not pattern.matches("log.txt")
    
    def test_subdirectory_pattern(self):
        """Test pattern with subdirectory like secret/*.key"""
        pattern = LLMIgnorePattern("secret/*.key")
        assert pattern.matches("secret/private.key")
        assert pattern.matches("secret/test.key")
        assert not pattern.matches("other/test.key")


class TestLLMIgnore:
    """Test LLMIgnore class."""
    
    def setup_method(self):
        """Set up test environment with temporary directory."""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_llmignore(self, content: str):
        """Helper to create .llmignore file with content."""
        ignore_file = os.path.join(self.test_dir, ".llmignore")
        with open(ignore_file, 'w') as f:
            f.write(content)
    
    def test_no_llmignore_file(self):
        """Test behavior when no .llmignore file exists."""
        llmignore = LLMIgnore(self.test_dir)
        assert not llmignore.is_ignored("test.py")
        assert not llmignore.is_ignored(".env")
    
    def test_simple_ignore(self):
        """Test simple file ignore."""
        self.create_llmignore("*.env\n.secret")
        llmignore = LLMIgnore(self.test_dir)
        
        assert llmignore.is_ignored(".env")
        assert llmignore.is_ignored("test.env")
        assert llmignore.is_ignored(".secret")
        assert not llmignore.is_ignored("config.yaml")
    
    def test_directory_ignore(self):
        """Test directory ignore."""
        self.create_llmignore("secrets/\nnode_modules/")
        llmignore = LLMIgnore(self.test_dir)
        
        assert llmignore.is_ignored("secrets", is_dir=True)
        assert llmignore.is_ignored("node_modules", is_dir=True)
        assert not llmignore.is_ignored("secrets", is_dir=False)
    
    def test_negation_pattern(self):
        """Test negation patterns."""
        self.create_llmignore("*.env\n!important.env")
        llmignore = LLMIgnore(self.test_dir)
        
        assert llmignore.is_ignored("test.env")
        assert not llmignore.is_ignored("important.env")
    
    def test_comments_and_empty_lines(self):
        """Test that comments and empty lines are ignored."""
        self.create_llmignore("""
# This is a comment
*.env

# Another comment
.secret
        """)
        llmignore = LLMIgnore(self.test_dir)
        
        assert llmignore.is_ignored(".env")
        assert llmignore.is_ignored(".secret")
    
    def test_anchored_patterns(self):
        """Test anchored patterns."""
        self.create_llmignore("/config.yaml\n/secrets/")
        llmignore = LLMIgnore(self.test_dir)
        
        assert llmignore.is_ignored("config.yaml")
        assert not llmignore.is_ignored("dir/config.yaml")
    
    def test_filter_files(self):
        """Test filtering a list of files."""
        self.create_llmignore("*.env\nsecrets/")
        llmignore = LLMIgnore(self.test_dir)
        
        files = ["test.py", "config.env", "data.json", ".env"]
        allowed, ignored = llmignore.filter_files(files)
        
        assert "test.py" in allowed
        assert "data.json" in allowed
        assert "config.env" in ignored
        assert ".env" in ignored
    
    def test_filter_with_subdirectories(self):
        """Test filtering files in subdirectories."""
        self.create_llmignore("*.log\nsecrets/*.key")
        llmignore = LLMIgnore(self.test_dir)
        
        files = [
            "app.py",
            "debug.log",
            "dir/test.log",
            "secrets/private.key",
            "secrets/config.json"
        ]
        allowed, ignored = llmignore.filter_files(files)
        
        assert "app.py" in allowed
        assert "secrets/config.json" in allowed
        assert "debug.log" in ignored
        assert "dir/test.log" in ignored
        assert "secrets/private.key" in ignored


class TestFilterAtContext:
    """Test filtering @ prefix context."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_llmignore(self, content: str):
        """Helper to create .llmignore file."""
        ignore_file = os.path.join(self.test_dir, ".llmignore")
        with open(ignore_file, 'w') as f:
            f.write(content)
    
    def test_filter_files_in_context(self):
        """Test filtering files from @ context."""
        self.create_llmignore("*.env\nsecrets/")
        
        at_context = {
            'files': ['test.py', 'config.env', '.env'],
            'directories': ['src', 'secrets'],
            'non_existing': []
        }
        
        filtered, ignored = filter_at_context(at_context, self.test_dir)
        
        assert 'test.py' in filtered['files']
        assert 'config.env' not in filtered['files']
        assert '.env' not in filtered['files']
        assert 'src' in filtered['directories']
        assert 'secrets' not in filtered['directories']
        
        assert 'config.env' in ignored['files']
        assert '.env' in ignored['files']
        assert 'secrets' in ignored['directories']
    
    def test_filter_with_negation(self):
        """Test filtering with negation patterns."""
        self.create_llmignore("*.env\n!important.env")
        
        at_context = {
            'files': ['test.env', 'important.env', 'config.yaml'],
            'directories': [],
            'non_existing': []
        }
        
        filtered, ignored = filter_at_context(at_context, self.test_dir)
        
        assert 'important.env' in filtered['files']
        assert 'config.yaml' in filtered['files']
        assert 'test.env' in ignored['files']


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_llmignore(self, content: str):
        """Helper to create .llmignore file."""
        ignore_file = os.path.join(self.test_dir, ".llmignore")
        with open(ignore_file, 'w') as f:
            f.write(content)
    
    def test_get_llmignore(self):
        """Test get_llmignore convenience function."""
        llmignore = get_llmignore(self.test_dir)
        assert isinstance(llmignore, LLMIgnore)
    
    def test_is_file_ignored(self):
        """Test is_file_ignored convenience function."""
        self.create_llmignore("*.env")
        
        assert is_file_ignored(".env", self.test_dir)
        assert not is_file_ignored("config.yaml", self.test_dir)


class TestRealWorldPatterns:
    """Test real-world .llmignore patterns."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_llmignore(self, content: str):
        """Helper to create .llmignore file."""
        ignore_file = os.path.join(self.test_dir, ".llmignore")
        with open(ignore_file, 'w') as f:
            f.write(content)
    
    def test_common_secrets(self):
        """Test common secret file patterns."""
        self.create_llmignore("""
# Environment files
.env
.env.*
*.env

# API keys
*_key
*_secret
*.pem
*.key

# Credentials
credentials.json
secrets.yaml
        """)
        llmignore = LLMIgnore(self.test_dir)
        
        # Should be ignored
        assert llmignore.is_ignored(".env")
        assert llmignore.is_ignored(".env.local")
        assert llmignore.is_ignored("production.env")
        assert llmignore.is_ignored("api_key")
        assert llmignore.is_ignored("db_secret")
        assert llmignore.is_ignored("private.pem")
        assert llmignore.is_ignored("server.key")
        assert llmignore.is_ignored("credentials.json")
        assert llmignore.is_ignored("secrets.yaml")
        
        # Should not be ignored
        assert not llmignore.is_ignored("config.yaml")
        assert not llmignore.is_ignored("README.md")
    
    def test_dependency_directories(self):
        """Test common dependency directory patterns."""
        self.create_llmignore("""
# Dependencies
node_modules/
venv/
.venv/
__pycache__/
*.pyc

# Build artifacts
dist/
build/
*.egg-info/
        """)
        llmignore = LLMIgnore(self.test_dir)
        
        # Should be ignored
        assert llmignore.is_ignored("node_modules", is_dir=True)
        assert llmignore.is_ignored("venv", is_dir=True)
        assert llmignore.is_ignored(".venv", is_dir=True)
        assert llmignore.is_ignored("__pycache__", is_dir=True)
        assert llmignore.is_ignored("test.pyc")
        assert llmignore.is_ignored("dist", is_dir=True)
        assert llmignore.is_ignored("build", is_dir=True)
        
        # Should not be ignored
        assert not llmignore.is_ignored("src", is_dir=True)
        assert not llmignore.is_ignored("test.py")


class TestHierarchicalIgnore:
    """Test hierarchical .llmignore files in subdirectories."""
    
    def setup_method(self):
        """Set up test environment with nested directories."""
        self.test_dir = tempfile.mkdtemp()
        self.sub_dir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.sub_dir)
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_subdirectory_llmignore(self):
        """Test .llmignore in subdirectory."""
        # Root .llmignore
        root_ignore = os.path.join(self.test_dir, ".llmignore")
        with open(root_ignore, 'w') as f:
            f.write("*.log\n")
        
        # Subdirectory .llmignore
        sub_ignore = os.path.join(self.sub_dir, ".llmignore")
        with open(sub_ignore, 'w') as f:
            f.write("*.tmp\n")
        
        # Test from root
        llmignore = LLMIgnore(self.test_dir)
        assert llmignore.is_ignored("test.log")
        
        # When filtering directory contents, subdirectory .llmignore should be checked
        files_content = [
            {'path': 'test.txt', 'content': 'data'},
            {'path': 'debug.log', 'content': 'logs'},
            {'path': 'cache.tmp', 'content': 'temp'}
        ]
        
        allowed, ignored = llmignore.filter_directory_contents(
            'subdir',
            files_content
        )
        
        # .tmp files should be filtered by subdirectory .llmignore
        assert any(f['path'] == 'test.txt' for f in allowed)
        assert 'cache.tmp' in ignored


class TestSecurityEdgeCases:
    """Test security-focused edge cases."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_llmignore(self, content: str):
        """Helper to create .llmignore file."""
        ignore_file = os.path.join(self.test_dir, ".llmignore")
        with open(ignore_file, 'w') as f:
            f.write(content)
    
    def test_explicit_file_still_ignored(self):
        """Test that explicitly requested files are still ignored if matched."""
        self.create_llmignore(".env")
        
        # Even if user explicitly uses @.env, it should be filtered
        at_context = {
            'files': ['.env'],
            'directories': [],
            'non_existing': []
        }
        
        filtered, ignored = filter_at_context(at_context, self.test_dir)
        
        # .env should be in ignored, not filtered
        assert '.env' not in filtered['files']
        assert '.env' in ignored['files']
    
    def test_case_sensitivity(self):
        """Test case-sensitive pattern matching."""
        self.create_llmignore("*.ENV")
        llmignore = LLMIgnore(self.test_dir)
        
        # Pattern matching should be case-sensitive on Unix, case-insensitive on Windows
        # fnmatch follows system conventions
        # We test that patterns work as expected
        assert llmignore.is_ignored("test.ENV")
    
    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are handled safely."""
        self.create_llmignore("*.env")
        llmignore = LLMIgnore(self.test_dir)
        
        # Even with path traversal attempts, patterns should work
        assert llmignore.is_ignored("../test.env")
        assert llmignore.is_ignored("dir/../config.env")
