"""
Integration tests for UI chat route handlers.

These tests verify the new command handlers:
- handle_clear()
- handle_repomap_create/load/update()
- handle_datamap_create/load/update()

Run with: pytest tests/test_ui_chat_routes.py -v
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# Import the chat blueprint and handlers
from src.ui.routes.chat import chat_bp, _call_llm_for_map


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def temp_working_dir(tmp_path):
    """Create a temporary working directory with test files."""
    # Create some test source files
    (tmp_path / "main.py").write_text("def main():\n    pass\n")
    (tmp_path / "utils.py").write_text("def helper():\n    return True\n")
    
    # Create a subdirectory with more files
    subdir = tmp_path / "src"
    subdir.mkdir()
    (subdir / "module.py").write_text("class MyClass:\n    pass\n")
    
    # Create some test data files
    (tmp_path / "data.csv").write_text("name,age\nAlice,30\nBob,25\n")
    (tmp_path / "config.json").write_text('{"key": "value"}\n')
    
    return tmp_path


@pytest.mark.unit
class TestCallLLMForMapHelper:
    """Test the _call_llm_for_map helper function."""
    
    def test_successful_llm_call_with_message_attr(self):
        """Test successful LLM call when response has message attribute."""
        mock_response = Mock()
        mock_response.message.content = "Test response content"
        
        mock_client = Mock()
        mock_client.chat.return_value = mock_response
        
        with patch('src.ui.routes.chat.get_ollama_client', return_value=(mock_client, {})):
            result = _call_llm_for_map("test prompt", "test system msg")
            
            assert result == "Test response content"
            mock_client.chat.assert_called_once()
            call_args = mock_client.chat.call_args
            assert call_args[1]['messages'][0]['role'] == 'system'
            assert call_args[1]['messages'][0]['content'] == 'test system msg'
            assert call_args[1]['messages'][1]['role'] == 'user'
            assert call_args[1]['messages'][1]['content'] == 'test prompt'
    
    def test_successful_llm_call_with_dict_response(self):
        """Test successful LLM call when response is a dictionary."""
        mock_response = {
            'message': {
                'content': 'Dictionary response content'
            }
        }
        
        mock_client = Mock()
        mock_client.chat.return_value = mock_response
        
        with patch('src.ui.routes.chat.get_ollama_client', return_value=(mock_client, {})):
            result = _call_llm_for_map("test prompt", "test system msg")
            
            assert result == "Dictionary response content"
    
    def test_llm_call_with_string_response(self):
        """Test LLM call when response is a plain string."""
        mock_client = Mock()
        mock_client.chat.return_value = "Plain string response"
        
        with patch('src.ui.routes.chat.get_ollama_client', return_value=(mock_client, {})):
            result = _call_llm_for_map("test prompt", "test system msg")
            
            assert result == "Plain string response"
    
    def test_llm_call_raises_exception(self):
        """Test LLM call when client raises an exception."""
        mock_client = Mock()
        mock_client.chat.side_effect = Exception("LLM service unavailable")
        
        with patch('src.ui.routes.chat.get_ollama_client', return_value=(mock_client, {})):
            with pytest.raises(Exception, match="LLM service unavailable"):
                _call_llm_for_map("test prompt", "test system msg")


@pytest.mark.integration
class TestHandleClear:
    """Test the /clear command handler."""
    
    @patch('src.ui.routes.chat.get_session_manager')
    def test_clear_creates_new_session(self, mock_get_session_manager, client):
        """Test that clear command creates a new session."""
        mock_session_manager = Mock()
        mock_session_manager.is_active.return_value = True
        mock_session_manager.get_session_id.return_value = "new-session-456"
        mock_session_manager.session_history = [{"role": "user", "content": "test"}]
        mock_get_session_manager.return_value = mock_session_manager
        
        response = client.post('/api/chat/command',
                              data=json.dumps({'command': '/clear'}),
                              content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['session_active'] is True
        assert data['session_id'] == 'new-session-456'
        assert '🗑️' in data['response']
        
        # Verify session was saved and ended
        mock_session_manager.save_to_redis.assert_called_once()
        mock_session_manager.end_session.assert_called_once()
        mock_session_manager.start_session.assert_called_once()
    
    @patch('src.ui.routes.chat.get_session_manager')
    def test_clear_without_active_session(self, mock_get_session_manager, client):
        """Test clear command when no session is active."""
        mock_session_manager = Mock()
        mock_session_manager.is_active.return_value = False
        mock_session_manager.get_session_id.return_value = "new-session-789"
        mock_get_session_manager.return_value = mock_session_manager
        
        response = client.post('/api/chat/command',
                              data=json.dumps({'command': '/clear'}),
                              content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['session_id'] == 'new-session-789'
        
        # Verify save was not called (no active session)
        mock_session_manager.save_to_redis.assert_not_called()
        mock_session_manager.end_session.assert_not_called()


@pytest.mark.integration
class TestHandleRepomapCreate:
    """Test the /repomap create command handler."""
    
    @patch('src.ui.routes.chat._call_llm_for_map')
    @patch('src.utils.repomap.generate_repomap_prompt')
    @patch('src.utils.tree.generate_tree')
    @patch('src.utils.repomap.collect_source_files')
    def test_repomap_create_success(self, mock_collect, mock_tree, mock_prompt, mock_llm, client, temp_working_dir):
        """Test successful repository map creation."""
        mock_collect.return_value = [
            {'path': 'main.py', 'extension': '.py'},
            {'path': 'utils.py', 'extension': '.py'}
        ]
        mock_tree.return_value = ".\n├── main.py\n└── utils.py"
        mock_prompt.return_value = "Generate a repomap for these files..."
        mock_llm.return_value = "# Repository Analysis\n\nThis repo contains Python modules."
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap create'}),
                                  content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'Repository map created successfully' in data['response']
        assert '2' in data['response']  # Should show 2 files found
        
        # Verify .repomap file was created
        repomap_path = temp_working_dir / '.repomap'
        assert repomap_path.exists()
        content = repomap_path.read_text()
        assert '# Repository Map' in content
        assert '## Directory Tree' in content
        assert 'Repository Analysis' in content
        
        # Verify LLM was called
        mock_llm.assert_called_once()
        assert 'repository maps' in mock_llm.call_args[1]['system_msg'].lower()
    
    @patch('src.utils.repomap.collect_source_files')
    def test_repomap_create_no_files(self, mock_collect, client, temp_working_dir):
        """Test repomap create when no source files are found."""
        mock_collect.return_value = []
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap create'}),
                                  content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'No source code files found' in data['message']
    
    @patch('src.ui.routes.chat._call_llm_for_map')
    @patch('src.utils.repomap.generate_repomap_prompt')
    @patch('src.utils.tree.generate_tree')
    @patch('src.utils.repomap.collect_source_files')
    def test_repomap_create_llm_error(self, mock_collect, mock_tree, mock_prompt, mock_llm, client, temp_working_dir):
        """Test repomap create when LLM call fails."""
        mock_collect.return_value = [{'path': 'main.py', 'extension': '.py'}]
        mock_tree.return_value = ".\n└── main.py"
        mock_prompt.return_value = "Generate a repomap..."
        mock_llm.side_effect = Exception("LLM connection failed")
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap create'}),
                                  content_type='application/json')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Error calling LLM' in data['message']


@pytest.mark.integration
class TestHandleRepomapLoad:
    """Test the /repomap load command handler."""
    
    def test_repomap_load_success(self, client, temp_working_dir):
        """Test successful repository map loading."""
        # Create a .repomap file
        repomap_content = "# Repository Map\n\nThis is test content for the repository map."
        (temp_working_dir / '.repomap').write_text(repomap_content)
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap load'}),
                                  content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'Repository map loaded' in data['response']
        assert 'Preview:' in data['response']
    
    def test_repomap_load_file_not_found(self, client, temp_working_dir):
        """Test loading repomap when file doesn't exist."""
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap load'}),
                                  content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'No `.repomap` file found' in data['message']
    
    def test_repomap_load_empty_file(self, client, temp_working_dir):
        """Test loading an empty repomap file."""
        (temp_working_dir / '.repomap').write_text('')
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap load'}),
                                  content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'empty' in data['message'].lower()


@pytest.mark.integration
class TestHandleRepomapUpdate:
    """Test the /repomap update command handler."""
    
    @patch('src.ui.routes.chat._call_llm_for_map')
    @patch('src.utils.repomap.generate_repomap_update_prompt')
    @patch('src.utils.tree.generate_tree')
    @patch('src.utils.repomap.collect_source_files')
    def test_repomap_update_success(self, mock_collect, mock_tree, mock_prompt, mock_llm, client, temp_working_dir):
        """Test successful repository map update."""
        # Create existing .repomap file
        (temp_working_dir / '.repomap').write_text("# Old Repository Map\n\nOld content.")
        
        mock_collect.return_value = [{'path': 'main.py', 'extension': '.py'}]
        mock_tree.return_value = ".\n└── main.py"
        mock_prompt.return_value = "Update the repomap..."
        mock_llm.return_value = "# Updated Repository Analysis\n\nNew content."
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap update'}),
                                  content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'updated successfully' in data['response']
        
        # Verify file was updated
        content = (temp_working_dir / '.repomap').read_text()
        assert '(Updated)' in content
        assert 'Updated Repository Analysis' in content
    
    def test_repomap_update_no_existing_file(self, client, temp_working_dir):
        """Test update when no existing repomap file."""
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap update'}),
                                  content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'No `.repomap` file found' in data['message']


@pytest.mark.integration
class TestHandleDatamapCreate:
    """Test the /datamap create command handler."""
    
    @patch('src.ui.routes.chat._call_llm_for_map')
    @patch('src.utils.datamap.generate_datamap_prompt')
    @patch('src.utils.datamap.collect_data_files')
    def test_datamap_create_success(self, mock_collect, mock_prompt, mock_llm, client, temp_working_dir):
        """Test successful data map creation."""
        mock_collect.return_value = [
            {'path': 'data.csv', 'extension': 'csv', 'format': 'CSV'},
            {'path': 'config.json', 'extension': 'json', 'format': 'JSON'}
        ]
        mock_prompt.return_value = "Generate a datamap for these files..."
        mock_llm.return_value = "# Data Analysis\n\nFound 2 data files."
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/datamap create'}),
                                  content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'Data map created successfully' in data['response']
        assert '2' in data['response']  # Should show 2 files
        
        # Verify .datamap file was created
        datamap_path = temp_working_dir / '.datamap'
        assert datamap_path.exists()
        content = datamap_path.read_text()
        assert '# Data Map' in content
        assert 'Data Analysis' in content
    
    @patch('src.utils.datamap.collect_data_files')
    def test_datamap_create_no_files(self, mock_collect, client, temp_working_dir):
        """Test datamap create when no data files found."""
        mock_collect.return_value = []
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/datamap create'}),
                                  content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'No data files found' in data['message']


@pytest.mark.integration
class TestHandleDatamapLoad:
    """Test the /datamap load command handler."""
    
    def test_datamap_load_success(self, client, temp_working_dir):
        """Test successful data map loading."""
        datamap_content = "# Data Map\n\nThis contains data file schemas."
        (temp_working_dir / '.datamap').write_text(datamap_content)
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/datamap load'}),
                                  content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'Data map loaded' in data['response']
    
    def test_datamap_load_not_found(self, client, temp_working_dir):
        """Test loading datamap when file doesn't exist."""
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/datamap load'}),
                                  content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'No `.datamap` file found' in data['message']


@pytest.mark.integration
class TestHandleDatamapUpdate:
    """Test the /datamap update command handler."""
    
    @patch('src.ui.routes.chat._call_llm_for_map')
    @patch('src.utils.datamap.generate_datamap_update_prompt')
    @patch('src.utils.datamap.collect_data_files')
    def test_datamap_update_success(self, mock_collect, mock_prompt, mock_llm, client, temp_working_dir):
        """Test successful data map update."""
        # Create existing .datamap file
        (temp_working_dir / '.datamap').write_text("# Old Data Map\n\nOld schemas.")
        
        mock_collect.return_value = [{'path': 'data.csv', 'extension': 'csv'}]
        mock_prompt.return_value = "Update the datamap..."
        mock_llm.return_value = "# Updated Data Analysis\n\nRefreshed schemas."
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/datamap update'}),
                                  content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'updated successfully' in data['response']
        
        # Verify file was updated
        content = (temp_working_dir / '.datamap').read_text()
        assert '(Updated)' in content
        assert 'Updated Data Analysis' in content
    
    def test_datamap_update_no_existing_file(self, client, temp_working_dir):
        """Test update when no existing datamap file."""
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/datamap update'}),
                                  content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'No `.datamap` file found' in data['message']


@pytest.mark.integration
class TestResponseFormatConsistency:
    """Test that all handlers return consistent response formats."""
    
    @patch('src.ui.routes.chat.get_session_manager')
    def test_clear_response_format(self, mock_session, client):
        """Test clear command response format."""
        mock_session_manager = Mock()
        mock_session_manager.is_active.return_value = False
        mock_session_manager.get_session_id.return_value = "test-session"
        mock_session.return_value = mock_session_manager
        
        response = client.post('/api/chat/command',
                              data=json.dumps({'command': '/clear'}),
                              content_type='application/json')
        
        data = json.loads(response.data)
        assert 'status' in data
        assert 'response' in data
        assert data['status'] in ['success', 'error']
        if data['status'] == 'success':
            assert 'session_active' in data
            assert 'session_id' in data
    
    @patch('src.utils.repomap.collect_source_files')
    def test_error_response_format(self, mock_collect, client, temp_working_dir):
        """Test error response format consistency."""
        mock_collect.return_value = []
        
        with patch.dict(os.environ, {'AI_CLI_CWD': str(temp_working_dir)}):
            response = client.post('/api/chat/command',
                                  data=json.dumps({'command': '/repomap create'}),
                                  content_type='application/json')
        
        data = json.loads(response.data)
        assert 'status' in data
        assert 'message' in data
        assert data['status'] == 'error'
        assert response.status_code >= 400
