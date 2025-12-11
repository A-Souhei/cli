"""Tests for /context commands."""

import os
import json
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch, mock_open
from rich.console import Console
from io import StringIO
import pytest

from src.cli.commands.context import (
    handle_context_metrics,
    handle_context_add_all_tools,
    handle_context_generate_todo_list,
    handle_context_load_todo_list,
    handle_context_save_todo_list,
    handle_context_generate_make_list,
    handle_context_load_make_list,
    handle_context_save_make_list
)


class TestContextMetrics:
    """Test /context metrics command."""
    
    def setup_method(self):
        """Set up test environment."""
        self.console = Console(file=StringIO())
        self.chat_manager = Mock()
        self.session_manager = Mock()
    
    def test_metrics_no_session(self):
        """Test metrics when no session is active."""
        # Mock chat messages
        self.chat_manager.get_messages.return_value = [
            {'role': 'user', 'content': 'test message'},
            {'role': 'assistant', 'content': 'response'}
        ]
        self.session_manager.is_active.return_value = False
        
        result = handle_context_metrics(self.console, self.chat_manager, self.session_manager)
        
        assert result is True
        self.chat_manager.get_messages.assert_called_once()
    
    def test_metrics_with_active_session(self):
        """Test metrics with active session."""
        # Mock chat messages
        self.chat_manager.get_messages.return_value = [
            {'role': 'user', 'content': 'test message'},
            {'role': 'system', 'content': 'system prompt'},  # Should be filtered
            {'role': 'assistant', 'content': 'response'}
        ]
        
        # Mock session
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_info.return_value = {
            'session_id': 'test-session-id-12345678901234567890',
            'num_interactions': 5
        }
        self.session_manager.session_metadata = {'key': 'value'}
        self.session_manager.session_history = [{'entry': 'data'}]
        self.session_manager.get_session_id.return_value = 'test-session-id'
        
        with patch('httpx.Client') as mock_client:
            # Mock Redis response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'contexts': [
                    {
                        'context_type': 'file',
                        'metadata': {'size': 1000},
                        'content': 'file content'
                    },
                    {
                        'context_type': 'directory',
                        'metadata': {'size': 2000},
                        'content': 'dir content'
                    }
                ]
            }
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            
            result = handle_context_metrics(self.console, self.chat_manager, self.session_manager)
        
        assert result is True
        self.chat_manager.get_messages.assert_called_once()
        self.session_manager.get_session_info.assert_called_once()
    
    def test_metrics_with_redis_error(self):
        """Test metrics when Redis fails."""
        self.chat_manager.get_messages.return_value = [
            {'role': 'user', 'content': 'test'}
        ]
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_info.return_value = {
            'session_id': 'test-id',
            'num_interactions': 1
        }
        self.session_manager.session_metadata = {}
        self.session_manager.session_history = []
        self.session_manager.get_session_id.return_value = 'test-id'
        
        with patch('httpx.Client') as mock_client:
            # Simulate Redis error
            mock_client.return_value.__enter__.return_value.get.side_effect = Exception("Redis error")
            
            result = handle_context_metrics(self.console, self.chat_manager, self.session_manager)
        
        # Should still succeed despite Redis error
        assert result is True


class TestContextAddAllTools:
    """Test /context add ALL_TOOLS command."""
    
    def setup_method(self):
        """Set up test environment."""
        self.console = Console(file=StringIO())
        self.session_manager = Mock()
        self.mcp_client = Mock()
        self.run_async = Mock()
        self.debug_print = Mock()
    
    def test_add_all_tools_success(self):
        """Test adding all tools successfully."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'
        
        # Mock tools
        mock_tools = [
            {
                'name': 'tool1',
                'mcp_name': 'test_mcp',
                'description': 'Test tool 1',
                'inputSchema': {
                    'properties': {
                        'param1': {'type': 'string', 'description': 'Parameter 1'}
                    },
                    'required': ['param1']
                }
            },
            {
                'name': 'tool2',
                'mcp_name': 'test_mcp',
                'description': 'Test tool 2',
                'inputSchema': {}
            }
        ]
        self.run_async.return_value = mock_tools
        
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            
            result = handle_context_add_all_tools(
                self.console, self.session_manager, self.mcp_client,
                self.run_async, self.debug_print, verbose=False
            )
        
        assert result is True
        self.run_async.assert_called_once()
    
    def test_add_all_tools_no_tools(self):
        """Test when no tools are found."""
        self.session_manager.is_active.return_value = False
        self.run_async.return_value = []
        
        result = handle_context_add_all_tools(
            self.console, self.session_manager, self.mcp_client,
            self.run_async, self.debug_print, verbose=False
        )
        
        assert result is True
        self.run_async.assert_called_once()
    
    def test_add_all_tools_redis_error(self):
        """Test when Redis fails."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'
        self.run_async.return_value = [{'name': 'tool', 'mcp_name': 'mcp', 'description': 'desc', 'inputSchema': {}}]
        
        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = Exception("Redis error")
            
            result = handle_context_add_all_tools(
                self.console, self.session_manager, self.mcp_client,
                self.run_async, self.debug_print, verbose=False
            )
        
        # Should handle error gracefully
        assert result is True


class TestContextLoadTodoList:
    """Test /context load TODO_LIST command."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
        self.session_manager = Mock()
        self.get_user_working_dir = Mock(return_value=self.test_dir)
        self.debug_print = Mock()
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_load_todo_list_success(self):
        """Test loading TODO_LIST successfully."""
        # Create .todo_list file
        todo_file = os.path.join(self.test_dir, '.todo_list')
        with open(todo_file, 'w') as f:
            f.write("# TODO_LIST\n1. Task 1\n2. Task 2\n")
        
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'
        
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            
            result = handle_context_load_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False
            )
        
        assert result is True
    
    def test_load_todo_list_file_not_found(self):
        """Test loading when file doesn't exist."""
        self.session_manager.is_active.return_value = True
        
        result = handle_context_load_todo_list(
            self.console, self.session_manager, self.get_user_working_dir,
            self.debug_print, verbose=False
        )
        
        assert result is True
    
    def test_load_todo_list_empty_file(self):
        """Test loading empty file."""
        todo_file = os.path.join(self.test_dir, '.todo_list')
        with open(todo_file, 'w') as f:
            f.write("")

        self.session_manager.is_active.return_value = True

        result = handle_context_load_todo_list(
            self.console, self.session_manager, self.get_user_working_dir,
            self.debug_print, verbose=False
        )

        assert result is True

    def test_load_todo_list_custom_path(self):
        """Test loading TODO_LIST from custom file path."""
        # Create custom todo file
        custom_file = os.path.join(self.test_dir, 'my_todos.md')
        with open(custom_file, 'w') as f:
            f.write("# TODO_LIST\n1. Custom Task 1\n2. Custom Task 2\n")

        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = handle_context_load_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False, file_path='my_todos.md'
            )

        assert result is True

    def test_load_todo_list_custom_path_with_at_prefix(self):
        """Test loading TODO_LIST from custom file path with @ prefix."""
        # Create custom todo file
        custom_file = os.path.join(self.test_dir, 'todos', 'project.md')
        os.makedirs(os.path.dirname(custom_file), exist_ok=True)
        with open(custom_file, 'w') as f:
            f.write("# TODO_LIST\n1. Task 1\n")

        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = handle_context_load_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False, file_path='@todos/project.md'
            )

        assert result is True

    def test_load_todo_list_absolute_path(self):
        """Test loading TODO_LIST from absolute file path."""
        # Create custom todo file
        custom_file = os.path.join(self.test_dir, 'absolute_todos.md')
        with open(custom_file, 'w') as f:
            f.write("# TODO_LIST\n1. Task 1\n")

        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = handle_context_load_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False, file_path=custom_file
            )

        assert result is True


class TestContextSaveTodoList:
    """Test /context save TODO_LIST command."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
        self.session_manager = Mock()
        self.get_user_working_dir = Mock(return_value=self.test_dir)
        self.debug_print = Mock()
    
    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_save_todo_list_success(self):
        """Test saving TODO_LIST successfully."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'
        
        todo_content = "# TODO_LIST\n1. Task 1\n2. Task 2\n"
        
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'context': {
                    'content': todo_content
                }
            }
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            
            result = handle_context_save_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False
            )
        
        assert result is True
        
        # Verify file was created
        todo_file = os.path.join(self.test_dir, '.todo_list')
        assert os.path.exists(todo_file)
        with open(todo_file, 'r') as f:
            assert f.read() == todo_content
    
    def test_save_todo_list_no_session(self):
        """Test saving when no session is active."""
        self.session_manager.is_active.return_value = False
        self.session_manager.get_session_id.return_value = None
        
        result = handle_context_save_todo_list(
            self.console, self.session_manager, self.get_user_working_dir,
            self.debug_print, verbose=False
        )
        
        assert result is True
    
    def test_save_todo_list_not_found(self):
        """Test saving when TODO_LIST not in context."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = handle_context_save_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False
            )

        assert result is True

    def test_save_todo_list_custom_path(self):
        """Test saving TODO_LIST to custom file path."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        todo_content = "# TODO_LIST\n1. Task 1\n2. Task 2\n"

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'context': {
                    'content': todo_content
                }
            }
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = handle_context_save_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False, file_path='my_todos.md'
            )

        assert result is True

        # Verify file was created with custom name
        custom_file = os.path.join(self.test_dir, 'my_todos.md')
        assert os.path.exists(custom_file)
        with open(custom_file, 'r') as f:
            assert f.read() == todo_content

    def test_save_todo_list_custom_path_with_at_prefix(self):
        """Test saving TODO_LIST to custom file path with @ prefix."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        todo_content = "# TODO_LIST\n1. Task\n"

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'context': {
                    'content': todo_content
                }
            }
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = handle_context_save_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False, file_path='@todos/project.md'
            )

        assert result is True

        # Verify file was created
        custom_file = os.path.join(self.test_dir, 'todos', 'project.md')
        assert os.path.exists(custom_file)
        with open(custom_file, 'r') as f:
            assert f.read() == todo_content

    def test_save_todo_list_absolute_path(self):
        """Test saving TODO_LIST to absolute file path."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        todo_content = "# TODO_LIST\n1. Task\n"
        custom_file = os.path.join(self.test_dir, 'absolute_todos.md')

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'context': {
                    'content': todo_content
                }
            }
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = handle_context_save_todo_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False, file_path=custom_file
            )

        assert result is True

        # Verify file was created
        assert os.path.exists(custom_file)
        with open(custom_file, 'r') as f:
            assert f.read() == todo_content


class TestContextGenerateTodoList:
    """Test /context add TODO_LIST command."""
    
    def setup_method(self):
        """Set up test environment."""
        self.console = Console(file=StringIO())
        self.session_manager = Mock()
        self.mcp_client = Mock()
        self.ollama_client = Mock()
        self.config = {}
        self.run_async = Mock()
        self.debug_print = Mock()
    
    def test_generate_todo_list_success(self):
        """Test generating TODO_LIST successfully."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'
        
        # Mock ALL_TOOLS already loaded
        with patch('httpx.Client') as mock_client:
            mock_list_response = Mock()
            mock_list_response.status_code = 200
            mock_list_response.json.return_value = {
                'contexts': [
                    {'path': 'ALL_TOOLS', 'context_type': 'tools'}
                ]
            }
            
            mock_get_response = Mock()
            mock_get_response.status_code = 200
            mock_get_response.json.return_value = {
                'context': {
                    'content': '# Tools\n## Tool1\nDescription'
                }
            }
            
            mock_store_response = Mock()
            mock_store_response.status_code = 200
            mock_store_response.json.return_value = {'status': 'success'}
            
            mock_http = Mock()
            mock_http.get.side_effect = [mock_list_response, mock_get_response]
            mock_http.post.return_value = mock_store_response
            mock_client.return_value.__enter__.return_value = mock_http
            
            # Mock LLM response
            self.ollama_client.chat.return_value = {
                'message': {
                    'content': '# TODO_LIST: Test Task\n\n1. Step 1 - [Tool: tool1]\n2. Step 2 - [LLM: reasoning]\n'
                }
            }
            
            result = handle_context_generate_todo_list(
                self.console, self.session_manager, self.mcp_client,
                self.ollama_client, self.config, self.run_async,
                self.debug_print, "Create a test application", verbose=False
            )
        
        assert result is True
        self.ollama_client.chat.assert_called_once()
    
    def test_generate_todo_list_loads_tools_first(self):
        """Test that ALL_TOOLS is loaded if not present."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'
        
        # Mock tools list
        self.run_async.return_value = [
            {'name': 'tool1', 'mcp_name': 'mcp', 'description': 'Test', 'inputSchema': {}}
        ]
        
        with patch('httpx.Client') as mock_client:
            # Mock empty context list (ALL_TOOLS not loaded)
            mock_list_response = Mock()
            mock_list_response.status_code = 200
            mock_list_response.json.return_value = {'contexts': []}
            
            mock_store_response = Mock()
            mock_store_response.status_code = 200
            mock_store_response.json.return_value = {'status': 'success'}
            
            mock_get_response = Mock()
            mock_get_response.status_code = 200
            mock_get_response.json.return_value = {
                'context': {'content': '# Tools\n'}
            }
            
            mock_http = Mock()
            mock_http.get.side_effect = [mock_list_response, mock_get_response]
            mock_http.post.return_value = mock_store_response
            mock_client.return_value.__enter__.return_value = mock_http
            
            self.ollama_client.chat.return_value = {
                'message': {'content': '# TODO_LIST\n1. Task\n'}
            }
            
            result = handle_context_generate_todo_list(
                self.console, self.session_manager, self.mcp_client,
                self.ollama_client, self.config, self.run_async,
                self.debug_print, "Test request", verbose=False
            )
        
        assert result is True
        self.run_async.assert_called()


class TestContextLoadMakeList:
    """Test /context load MAKE_LIST command."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
        self.session_manager = Mock()
        self.get_user_working_dir = Mock(return_value=self.test_dir)
        self.debug_print = Mock()

    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_load_make_list_success(self):
        """Test loading MAKE_LIST successfully."""
        # Create .make_list file
        make_file = os.path.join(self.test_dir, '.make_list')
        with open(make_file, 'w') as f:
            f.write("# MAKE_LIST\n1. make test\n2. make build\n")

        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = handle_context_load_make_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False
            )

        assert result is True

    def test_load_make_list_file_not_found(self):
        """Test loading when file doesn't exist."""
        self.session_manager.is_active.return_value = True

        result = handle_context_load_make_list(
            self.console, self.session_manager, self.get_user_working_dir,
            self.debug_print, verbose=False
        )

        assert result is True

    def test_load_make_list_custom_path(self):
        """Test loading MAKE_LIST from custom file path."""
        # Create custom make file
        custom_file = os.path.join(self.test_dir, 'my_makes.md')
        with open(custom_file, 'w') as f:
            f.write("# MAKE_LIST\n1. make setup\n")

        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = handle_context_load_make_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False, file_path='my_makes.md'
            )

        assert result is True


class TestContextSaveMakeList:
    """Test /context save MAKE_LIST command."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
        self.session_manager = Mock()
        self.get_user_working_dir = Mock(return_value=self.test_dir)
        self.debug_print = Mock()

    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_make_list_success(self):
        """Test saving MAKE_LIST successfully."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        make_content = "# MAKE_LIST\n1. make test\n2. make build\n"

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'context': {
                    'content': make_content
                }
            }
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = handle_context_save_make_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False
            )

        assert result is True

        # Verify file was created
        make_file = os.path.join(self.test_dir, '.make_list')
        assert os.path.exists(make_file)
        with open(make_file, 'r') as f:
            assert f.read() == make_content

    def test_save_make_list_no_session(self):
        """Test saving when no session is active."""
        self.session_manager.is_active.return_value = False
        self.session_manager.get_session_id.return_value = None

        result = handle_context_save_make_list(
            self.console, self.session_manager, self.get_user_working_dir,
            self.debug_print, verbose=False
        )

        assert result is True

    def test_save_make_list_custom_path(self):
        """Test saving MAKE_LIST to custom file path."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        make_content = "# MAKE_LIST\n1. make deploy\n"

        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'context': {
                    'content': make_content
                }
            }
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = handle_context_save_make_list(
                self.console, self.session_manager, self.get_user_working_dir,
                self.debug_print, verbose=False, file_path='my_makes.md'
            )

        assert result is True

        # Verify file was created with custom name
        custom_file = os.path.join(self.test_dir, 'my_makes.md')
        assert os.path.exists(custom_file)
        with open(custom_file, 'r') as f:
            assert f.read() == make_content


class TestContextGenerateMakeList:
    """Test /context add MAKE_LIST command."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.console = Console(file=StringIO())
        self.session_manager = Mock()
        self.ollama_client = Mock()
        self.config = {}
        self.run_async = Mock()
        self.debug_print = Mock()
        self.get_user_working_dir = Mock(return_value=self.test_dir)

    def teardown_method(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_generate_make_list_no_makefile(self):
        """Test generating MAKE_LIST when no Makefile exists."""
        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        result = handle_context_generate_make_list(
            self.console, self.session_manager, self.ollama_client,
            self.config, self.run_async, self.debug_print,
            "Build and test the project", self.get_user_working_dir,
            verbose=False
        )

        # Should gracefully fail when no Makefile
        assert result is True

    def test_generate_make_list_with_existing_makemap(self):
        """Test generating MAKE_LIST with existing .makemap."""
        # Create a Makefile
        makefile_path = os.path.join(self.test_dir, 'Makefile')
        with open(makefile_path, 'w') as f:
            f.write("test:\n\t@echo 'Running tests'\n")

        # Create a .makemap file
        makemap_path = os.path.join(self.test_dir, '.makemap')
        with open(makemap_path, 'w') as f:
            f.write("## make test\nRuns the test suite\n")

        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        with patch('httpx.Client') as mock_client:
            mock_store_response = Mock()
            mock_store_response.status_code = 200
            mock_store_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_store_response

            # Mock LLM response
            self.ollama_client.chat.return_value = {
                'message': {
                    'content': '# MAKE_LIST: Test and Build\n\n1. Run tests - [Make: make test]\n'
                }
            }

            result = handle_context_generate_make_list(
                self.console, self.session_manager, self.ollama_client,
                self.config, self.run_async, self.debug_print,
                "Test and build", self.get_user_working_dir,
                verbose=False
            )

        assert result is True
        self.ollama_client.chat.assert_called_once()

    def test_generate_make_list_without_makemap_generates_it(self):
        """Test generating MAKE_LIST when Makefile exists but .makemap doesn't - should auto-generate makemap."""
        # Create a Makefile
        makefile_path = os.path.join(self.test_dir, 'Makefile')
        with open(makefile_path, 'w') as f:
            f.write("test:\n\t@echo 'Running tests'\n\nbuild:\n\t@echo 'Building'\n")

        # Don't create .makemap - it should be generated automatically
        makemap_path = os.path.join(self.test_dir, '.makemap')
        assert not os.path.exists(makemap_path)

        self.session_manager.is_active.return_value = True
        self.session_manager.get_session_id.return_value = 'test-session'

        with patch('httpx.Client') as mock_client:
            mock_store_response = Mock()
            mock_store_response.status_code = 200
            mock_store_response.json.return_value = {'status': 'success'}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_store_response

            # Mock LLM response for both makemap generation and MAKE_LIST generation
            # First call generates makemap, second call generates MAKE_LIST
            self.ollama_client.chat.side_effect = [
                {
                    'message': {
                        'content': '## make test\nRuns the test suite\n\n## make build\nBuilds the project\n'
                    }
                },
                {
                    'message': {
                        'content': '# MAKE_LIST: Test and Build\n\n1. Run tests - [Make: make test]\n2. Build project - [Make: make build]\n'
                    }
                }
            ]

            result = handle_context_generate_make_list(
                self.console, self.session_manager, self.ollama_client,
                self.config, self.run_async, self.debug_print,
                "Test and build", self.get_user_working_dir,
                verbose=False
            )

        assert result is True
        # Should be called twice - once for makemap, once for MAKE_LIST
        assert self.ollama_client.chat.call_count == 2
        # Verify .makemap was created
        assert os.path.exists(makemap_path)
