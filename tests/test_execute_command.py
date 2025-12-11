"""Tests for /execute command with @file shortcut."""

import os
import tempfile
import shutil
from unittest.mock import Mock, patch
from io import StringIO

import pytest
from rich.console import Console

from src.cli.commands.execute import (
    execute_plan_from_file,
    handle_execute_plan,
    parse_tool_reference,
)


class TestExecutePlanFromFile:
    """Test execute_plan_from_file function with various file formats."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
        self.get_user_working_dir = Mock(return_value=self.test_dir)
        self.debug_print = Mock()
        self.mcp_client = Mock()
        self.run_async = Mock()
        
        # Mock CustomMarkdown
        self.CustomMarkdown = Mock()
        
        # Mock OllamaClient
        self.ollama_client = Mock()
        self.ollama_client.model = "test-model"
        self.ollama_client.chat = Mock(return_value={
            'message': {'content': 'Step executed successfully'}
        })
        
        # Mock config
        self.config = Mock()
        self.config.get_system_prompt = Mock(return_value="Test system prompt")
        
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_execute_todo_list_from_file(self):
        """Test executing a TODO_LIST from a file."""
        # Create a TODO_LIST file
        todo_file = os.path.join(self.test_dir, 'test_todos.md')
        with open(todo_file, 'w') as f:
            f.write("""# TODO_LIST

1. First task to complete
2. Second task with details
3. Third task for testing
""")
        
        result = execute_plan_from_file(
            self.console, todo_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True
        # Verify LLM was called for each step (no tool references)
        assert self.ollama_client.chat.call_count == 3
    
    def test_execute_make_list_from_file(self):
        """Test executing a MAKE_LIST from a file."""
        # Create a MAKE_LIST file
        make_file = os.path.join(self.test_dir, 'test_makes.md')
        with open(make_file, 'w') as f:
            f.write("""# MAKE_LIST

1. Setup development environment
2. Install dependencies
3. Run tests
""")
        
        result = execute_plan_from_file(
            self.console, make_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True
        assert self.ollama_client.chat.call_count == 3
    
    def test_execute_file_with_relative_path(self):
        """Test executing a file with relative path."""
        # Create a file with relative path
        relative_file = 'relative_todos.md'
        full_path = os.path.join(self.test_dir, relative_file)
        with open(full_path, 'w') as f:
            f.write("""# TODO_LIST

- Task one
- Task two
""")
        
        result = execute_plan_from_file(
            self.console, relative_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True
        assert self.ollama_client.chat.call_count == 2
    
    def test_execute_file_not_found(self):
        """Test executing a non-existent file."""
        non_existent_file = os.path.join(self.test_dir, 'missing.md')
        
        result = execute_plan_from_file(
            self.console, non_existent_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True
        # LLM should not be called for non-existent file
        assert self.ollama_client.chat.call_count == 0
    
    def test_execute_empty_file(self):
        """Test executing an empty file."""
        empty_file = os.path.join(self.test_dir, 'empty.md')
        with open(empty_file, 'w') as f:
            f.write("")
        
        result = execute_plan_from_file(
            self.console, empty_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True
        assert self.ollama_client.chat.call_count == 0
    
    def test_execute_file_with_make_reference(self):
        """Test executing a file with [Make: target] reference."""
        make_file = os.path.join(self.test_dir, 'with_make.md')
        with open(make_file, 'w') as f:
            f.write("""# TODO_LIST

1. Build project [Make: make build]
2. Run tests [Make: make test]
""")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Build successful",
                stderr=""
            )
            
            result = execute_plan_from_file(
                self.console, make_file, self.get_user_working_dir,
                self.mcp_client, self.run_async, self.debug_print,
                self.CustomMarkdown, self.ollama_client, self.config,
                stream=False, temperature=0.7
            )
        
        assert result is True
        # Make commands should be called, not LLM
        assert mock_run.call_count == 2
        assert self.ollama_client.chat.call_count == 0
    
    def test_execute_file_with_tool_reference(self):
        """Test executing a file with [Tool: tool_name] reference."""
        tool_file = os.path.join(self.test_dir, 'with_tool.md')
        with open(tool_file, 'w') as f:
            f.write("""# TODO_LIST

1. Run code analysis [Tool: analyze_code]
2. Format code [Tool: format_code]
""")
        
        self.run_async.return_value = "Tool executed successfully"
        
        result = execute_plan_from_file(
            self.console, tool_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True
        # MCP tools should be called
        assert self.run_async.call_count == 2
        assert self.ollama_client.chat.call_count == 0
    
    def test_execute_file_with_different_bullet_styles(self):
        """Test executing a file with different bullet point styles."""
        bullet_file = os.path.join(self.test_dir, 'bullets.md')
        with open(bullet_file, 'w') as f:
            f.write("""# TODO_LIST

- Task with dash
* Task with asterisk
• Task with bullet point
1. Task with number
2. Another numbered task
""")
        
        result = execute_plan_from_file(
            self.console, bullet_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True
        # Should parse all 5 tasks
        assert self.ollama_client.chat.call_count == 5
    
    def test_execute_file_auto_detect_type(self):
        """Test auto-detection of plan type from filename."""
        # Test TODO detection from filename
        todo_file = os.path.join(self.test_dir, 'my_todo.md')
        with open(todo_file, 'w') as f:
            f.write("- Task one\n- Task two")
        
        result = execute_plan_from_file(
            self.console, todo_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True
        
        # Test MAKE detection from filename
        make_file = os.path.join(self.test_dir, 'make_plan.md')
        with open(make_file, 'w') as f:
            f.write("- Step one\n- Step two")
        
        self.ollama_client.chat.reset_mock()
        
        result = execute_plan_from_file(
            self.console, make_file, self.get_user_working_dir,
            self.mcp_client, self.run_async, self.debug_print,
            self.CustomMarkdown, self.ollama_client, self.config,
            stream=False, temperature=0.7
        )
        
        assert result is True


class TestHandleExecutePlan:
    """Test handle_execute_plan function with @ prefix."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
        self.session_manager = Mock()
        self.get_user_working_dir = Mock(return_value=self.test_dir)
        self.debug_print = Mock()
        self.mcp_client = Mock()
        self.run_async = Mock()
        
        # Mock CustomMarkdown
        self.CustomMarkdown = Mock()
        
        # Mock OllamaClient
        self.ollama_client = Mock()
        self.ollama_client.model = "test-model"
        
        # Mock config
        self.config = Mock()
        self.config.get_system_prompt = Mock(return_value="Test system prompt")
        
        # Session manager setup
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_info.return_value = {
            'session_id': 'test-session-12345',
            'title': 'Test Session'
        }
        
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_execute_with_at_prefix(self):
        """Test /execute @path/to/file.md command."""
        # Create a test file
        test_file = os.path.join(self.test_dir, 'test_plan.md')
        with open(test_file, 'w') as f:
            f.write("# TODO_LIST\n- Task one\n- Task two")
        
        with patch('src.cli.commands.execute.execute_plan_from_file') as mock_execute:
            mock_execute.return_value = True
            
            result = handle_execute_plan(
                self.console,
                self.session_manager,
                self.mcp_client,
                self.get_user_working_dir,
                self.run_async,
                '/execute @test_plan.md',
                self.debug_print,
                self.CustomMarkdown,
                self.ollama_client,
                self.config,
                stream=False,
                temperature=0.7
            )
        
        assert result is True
        mock_execute.assert_called_once()
        # Verify the @ prefix was stripped
        called_path = mock_execute.call_args[0][1]
        assert not called_path.startswith('@')
        assert called_path == 'test_plan.md'
    
    def test_execute_with_at_prefix_absolute_path(self):
        """Test /execute @/absolute/path/to/file.md command."""
        # Create a test file
        test_file = os.path.join(self.test_dir, 'absolute_plan.md')
        with open(test_file, 'w') as f:
            f.write("# TODO_LIST\n- Task one")
        
        with patch('src.cli.commands.execute.execute_plan_from_file') as mock_execute:
            mock_execute.return_value = True
            
            result = handle_execute_plan(
                self.console,
                self.session_manager,
                self.mcp_client,
                self.get_user_working_dir,
                self.run_async,
                f'/execute @{test_file}',
                self.debug_print,
                self.CustomMarkdown,
                self.ollama_client,
                self.config,
                stream=False,
                temperature=0.7
            )
        
        assert result is True
        mock_execute.assert_called_once()
        # Verify the @ prefix was stripped but absolute path preserved
        called_path = mock_execute.call_args[0][1]
        assert not called_path.startswith('@')
        assert called_path == test_file
    
    def test_execute_with_at_prefix_dotfile(self):
        """Test /execute @.todo_list command."""
        # Create .todo_list file
        dotfile = os.path.join(self.test_dir, '.todo_list')
        with open(dotfile, 'w') as f:
            f.write("# TODO_LIST\n- Task one\n- Task two\n- Task three")
        
        with patch('src.cli.commands.execute.execute_plan_from_file') as mock_execute:
            mock_execute.return_value = True
            
            result = handle_execute_plan(
                self.console,
                self.session_manager,
                self.mcp_client,
                self.get_user_working_dir,
                self.run_async,
                '/execute @.todo_list',
                self.debug_print,
                self.CustomMarkdown,
                self.ollama_client,
                self.config,
                stream=False,
                temperature=0.7
            )
        
        assert result is True
        mock_execute.assert_called_once()
        called_path = mock_execute.call_args[0][1]
        assert called_path == '.todo_list'
    
    def test_execute_without_at_prefix_todo_list(self):
        """Test /execute TODO_LIST command (without @ prefix)."""
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'plan': 'TODO_LIST\n1. Task one\n2. Task two',
                'steps': ['Task one', 'Task two']
            }
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            
            result = handle_execute_plan(
                self.console,
                self.session_manager,
                self.mcp_client,
                self.get_user_working_dir,
                self.run_async,
                '/execute TODO_LIST',
                self.debug_print,
                self.CustomMarkdown,
                self.ollama_client,
                self.config,
                stream=False,
                temperature=0.7
            )
        
        # This should use the API endpoint, not execute_plan_from_file
        assert result is True
    
    def test_execute_no_session(self):
        """Test /execute when no session is active."""
        self.session_manager.is_active.return_value = False
        
        result = handle_execute_plan(
            self.console,
            self.session_manager,
            self.mcp_client,
            self.get_user_working_dir,
            self.run_async,
            '/execute @test.md',
            self.debug_print,
            self.CustomMarkdown,
            self.ollama_client,
            self.config,
            stream=False,
            temperature=0.7
        )
        
        assert result is True
    
    def test_execute_no_argument(self):
        """Test /execute with no argument."""
        result = handle_execute_plan(
            self.console,
            self.session_manager,
            self.mcp_client,
            self.get_user_working_dir,
            self.run_async,
            '/execute',
            self.debug_print,
            self.CustomMarkdown,
            self.ollama_client,
            self.config,
            stream=False,
            temperature=0.7
        )
        
        assert result is True


class TestParseToolReference:
    """Test parse_tool_reference function."""
    
    def test_parse_tool_reference_tool(self):
        """Test parsing [Tool: tool_name] reference."""
        tool_type, tool_name = parse_tool_reference("Step with [Tool: analyze_code] reference")
        assert tool_type == 'tool'
        assert tool_name == 'analyze_code'
    
    def test_parse_tool_reference_make(self):
        """Test parsing [Make: make target] reference."""
        tool_type, tool_name = parse_tool_reference("Build project [Make: make build]")
        assert tool_type == 'make'
        assert tool_name == 'build'
    
    def test_parse_tool_reference_make_with_args(self):
        """Test parsing [Make: make target] with arguments."""
        tool_type, tool_name = parse_tool_reference("Test [Make: make test-unit]")
        assert tool_type == 'make'
        assert tool_name == 'test-unit'
    
    def test_parse_tool_reference_none(self):
        """Test parsing step with no tool reference."""
        tool_type, tool_name = parse_tool_reference("Regular step without any tool")
        assert tool_type is None
        assert tool_name is None
    
    def test_parse_tool_reference_case_insensitive(self):
        """Test that parsing is case insensitive."""
        tool_type, tool_name = parse_tool_reference("Step with [TOOL: format_code]")
        assert tool_type == 'tool'
        assert tool_name == 'format_code'
        
        tool_type, tool_name = parse_tool_reference("Build [MAKE: make clean]")
        assert tool_type == 'make'
        assert tool_name == 'clean'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
