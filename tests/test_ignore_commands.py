"""Tests for /ignore commands."""

import os
import tempfile
import shutil
from rich.console import Console
from io import StringIO

from src.cli.commands.ignore import (
    handle_ignore_create,
    handle_ignore_add,
    handle_ignore_command
)


class TestIgnoreCreate:
    """Test /ignore create command."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_create_llmignore(self):
        """Test creating .llmignore file."""
        result = handle_ignore_create(self.console, self.test_dir)
        
        assert result is True
        assert os.path.exists(os.path.join(self.test_dir, '.llmignore'))
        
        # Verify content
        with open(os.path.join(self.test_dir, '.llmignore'), 'r') as f:
            content = f.read()
            assert '.env' in content
            assert 'node_modules/' in content
            assert '# .llmignore' in content
    
    def test_create_llmignore_already_exists(self):
        """Test creating .llmignore when it already exists."""
        # Create file first
        llmignore_path = os.path.join(self.test_dir, '.llmignore')
        with open(llmignore_path, 'w') as f:
            f.write('existing content\n')
        
        result = handle_ignore_create(self.console, self.test_dir)
        
        assert result is True
        # File should not be overwritten
        with open(llmignore_path, 'r') as f:
            content = f.read()
            assert content == 'existing content\n'


class TestIgnoreAdd:
    """Test /ignore add command."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
        
        # Create .llmignore file
        self.llmignore_path = os.path.join(self.test_dir, '.llmignore')
        with open(self.llmignore_path, 'w') as f:
            f.write('# Existing patterns\n.env\n')
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_add_single_file(self):
        """Test adding a single file to .llmignore."""
        result = handle_ignore_add(self.console, self.test_dir, '/ignore add @secrets.txt')
        
        assert result is True
        with open(self.llmignore_path, 'r') as f:
            content = f.read()
            assert 'secrets.txt' in content
            assert '.env' in content  # Original content preserved
    
    def test_add_multiple_files(self):
        """Test adding multiple files to .llmignore."""
        result = handle_ignore_add(self.console, self.test_dir,
                                   '/ignore add @api.key @credentials.json')
        
        assert result is True
        with open(self.llmignore_path, 'r') as f:
            content = f.read()
            assert 'api.key' in content
            assert 'credentials.json' in content
    
    def test_add_duplicate_file(self):
        """Test adding a file that already exists in .llmignore."""
        result = handle_ignore_add(self.console, self.test_dir, '/ignore add @.env')
        
        assert result is True
        # Check that .env appears only once
        with open(self.llmignore_path, 'r') as f:
            content = f.read()
            # Should only be one occurrence in non-comment lines
            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
            assert lines.count('.env') == 1
    
    def test_add_without_llmignore(self):
        """Test adding files when .llmignore doesn't exist."""
        # Remove .llmignore
        os.remove(self.llmignore_path)
        
        result = handle_ignore_add(self.console, self.test_dir, '/ignore add @test.txt')
        
        assert result is True
        # File should not be created
        assert not os.path.exists(self.llmignore_path)
    
    def test_add_no_files_specified(self):
        """Test add command without specifying files."""
        result = handle_ignore_add(self.console, self.test_dir, '/ignore add')
        
        assert result is True
        # .llmignore should not be modified
        with open(self.llmignore_path, 'r') as f:
            content = f.read()
            assert content == '# Existing patterns\n.env\n'


class TestIgnoreCommand:
    """Test main ignore command handler."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_ignore_create_command(self):
        """Test /ignore create routing."""
        result = handle_ignore_command(self.console, self.test_dir, '/ignore create')
        
        assert result is True
        assert os.path.exists(os.path.join(self.test_dir, '.llmignore'))
    
    def test_ignore_add_command(self):
        """Test /ignore add routing."""
        # Create .llmignore first
        with open(os.path.join(self.test_dir, '.llmignore'), 'w') as f:
            f.write('.env\n')
        
        result = handle_ignore_command(self.console, self.test_dir,
                                       '/ignore add @test.txt')
        
        assert result is True
        with open(os.path.join(self.test_dir, '.llmignore'), 'r') as f:
            content = f.read()
            assert 'test.txt' in content
    
    def test_unknown_ignore_command(self):
        """Test unknown /ignore subcommand."""
        result = handle_ignore_command(self.console, self.test_dir, '/ignore unknown')
        
        assert result is True  # Still handled, shows help
    
    def test_non_ignore_command(self):
        """Test non-ignore command."""
        result = handle_ignore_command(self.console, self.test_dir, '/other command')
        
        assert result is False  # Not handled
