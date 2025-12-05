"""Tests for file action handler."""

import pytest
from src.utils.file_action_handler import (
    detect_file_actions,
    generate_file_modification_instructions,
    generate_file_context_message,
    generate_target_file_message,
    generate_execution_message,
    build_system_messages
)
from src.config import ConfigManager


class TestFileActionDetection:
    """Test action keyword detection."""

    def test_detect_import_action(self):
        """Test detection of import action."""
        config = ConfigManager()
        at_context = {
            'files': ['services/user_service.py'],
            'non_existing': [],
            'directories': []
        }
        user_input = "import @utils/helpers.py validate_email into @services/user_service.py"

        result = detect_file_actions(user_input, at_context, config)

        assert result['has_action'] is True
        assert 'import' in result['action_keywords_found']
        assert 'services/user_service.py' in result['files_to_modify']

    def test_detect_create_action(self):
        """Test detection of create action."""
        config = ConfigManager()
        at_context = {
            'files': [],
            'non_existing': ['new_file.py'],
            'directories': []
        }
        user_input = "create @new_file.py with a function"

        result = detect_file_actions(user_input, at_context, config)

        assert result['has_action'] is True
        assert 'create' in result['action_keywords_found']
        assert 'new_file.py' in result['files_to_create']

    def test_detect_refactor_action(self):
        """Test detection of refactor action."""
        config = ConfigManager()
        at_context = {
            'files': ['app.py'],
            'non_existing': [],
            'directories': []
        }
        user_input = "refactor @app.py to use async functions"

        result = detect_file_actions(user_input, at_context, config)

        assert result['has_action'] is True
        assert 'refactor' in result['action_keywords_found']
        assert 'app.py' in result['files_to_modify']

    def test_no_action_keywords(self):
        """Test when no action keywords present."""
        config = ConfigManager()
        at_context = {'files': [], 'non_existing': [], 'directories': []}
        user_input = "what is this file about?"

        result = detect_file_actions(user_input, at_context, config)

        assert result['has_action'] is False
        assert len(result['action_keywords_found']) == 0

    def test_create_pattern_extraction(self):
        """Test extraction of create pattern without @ prefix."""
        config = ConfigManager()
        at_context = {'files': [], 'non_existing': [], 'directories': []}
        user_input = "create base.py file"

        result = detect_file_actions(user_input, at_context, config)

        assert result['has_action'] is True
        assert 'base.py' in result['files_to_create']


class TestInstructionGeneration:
    """Test instruction string generation."""

    def test_generate_modify_instructions(self):
        """Test generating instructions for file modification."""
        instruction = generate_file_modification_instructions(
            files_to_modify=['app.py'],
            files_to_create=[]
        )

        assert 'MODIFY these existing files: app.py' in instruction
        assert 'file: <full_file_path>' in instruction
        assert 'IMPORTANT' in instruction

    def test_generate_create_instructions(self):
        """Test generating instructions for file creation."""
        instruction = generate_file_modification_instructions(
            files_to_modify=[],
            files_to_create=['new_file.py']
        )

        assert 'CREATE these new files: new_file.py' in instruction
        assert 'file: <full_file_path>' in instruction

    def test_generate_both_modify_and_create(self):
        """Test generating instructions for both modify and create."""
        instruction = generate_file_modification_instructions(
            files_to_modify=['app.py'],
            files_to_create=['new_file.py']
        )

        assert 'MODIFY these existing files: app.py' in instruction
        assert 'CREATE these new files: new_file.py' in instruction

    def test_empty_lists_return_empty_string(self):
        """Test that empty lists return empty string."""
        instruction = generate_file_modification_instructions(
            files_to_modify=[],
            files_to_create=[]
        )

        assert instruction == ""


class TestContextMessages:
    """Test context message generation."""

    def test_generate_file_context_message(self):
        """Test generating file context message."""
        context_parts = ['File: app.py\nContent here', 'File: utils.py\nHelper functions']
        
        msg = generate_file_context_message(context_parts)
        
        assert msg is not None
        assert msg['role'] == 'system'
        assert 'app.py' in msg['content']
        assert 'utils.py' in msg['content']

    def test_generate_file_context_message_empty(self):
        """Test generating file context message with empty list."""
        msg = generate_file_context_message([])
        assert msg is None

    def test_generate_target_file_message_python(self):
        """Test generating target file message for Python."""
        msg = generate_target_file_message('test.py')
        
        assert msg is not None
        assert msg['role'] == 'system'
        assert 'test.py' in msg['content']
        assert 'Python' in msg['content']

    def test_generate_target_file_message_r(self):
        """Test generating target file message for R."""
        msg = generate_target_file_message('script.R')
        
        assert msg is not None
        assert msg['role'] == 'system'
        assert 'script.R' in msg['content']
        assert 'R' in msg['content']

    def test_generate_target_file_message_none(self):
        """Test generating target file message with None."""
        msg = generate_target_file_message(None)
        assert msg is None

    def test_generate_execution_message(self):
        """Test generating execution message."""
        msg = generate_execution_message('run this code')
        
        assert msg is not None
        assert msg['role'] == 'system'
        assert 'execute' in msg['content'].lower()

    def test_generate_execution_message_no_keyword(self):
        """Test generating execution message without keywords."""
        msg = generate_execution_message('show me the code')
        assert msg is None


class TestBuildSystemMessages:
    """Test building complete system messages."""

    def test_build_with_file_action(self):
        """Test building system messages with file action."""
        config = ConfigManager()
        at_context = {
            'files': ['app.py'],
            'non_existing': [],
            'directories': []
        }
        user_input = "refactor @app.py"
        
        messages = build_system_messages(
            at_context=at_context,
            user_input=user_input,
            config=config
        )
        
        # Should have at least one message for file modification
        assert len(messages) > 0
        assert any('MODIFY' in msg['content'] for msg in messages)

    def test_build_with_context_parts(self):
        """Test building system messages with context parts."""
        config = ConfigManager()
        at_context = {'files': [], 'non_existing': [], 'directories': []}
        user_input = "help me"
        context_parts = ['File content here']
        
        messages = build_system_messages(
            at_context=at_context,
            user_input=user_input,
            config=config,
            injected_context_parts=context_parts
        )
        
        assert len(messages) > 0
        assert any('File content here' in msg['content'] for msg in messages)

    def test_build_with_target_file(self):
        """Test building system messages with target file."""
        config = ConfigManager()
        at_context = {'files': [], 'non_existing': [], 'directories': []}
        user_input = "write a function"
        
        messages = build_system_messages(
            at_context=at_context,
            user_input=user_input,
            config=config,
            target_file='output.py'
        )
        
        assert len(messages) > 0
        assert any('output.py' in msg['content'] for msg in messages)

    def test_build_with_session_context(self):
        """Test building system messages with session context."""
        config = ConfigManager()
        at_context = {'files': [], 'non_existing': [], 'directories': []}
        user_input = "continue"
        
        messages = build_system_messages(
            at_context=at_context,
            user_input=user_input,
            config=config,
            session_context='Previous conversation...'
        )
        
        assert len(messages) > 0
        assert any('Previous conversation' in msg['content'] for msg in messages)

    def test_build_with_guidance(self):
        """Test building system messages with guidance."""
        config = ConfigManager()
        at_context = {'files': [], 'non_existing': [], 'directories': []}
        user_input = "help"
        
        messages = build_system_messages(
            at_context=at_context,
            user_input=user_input,
            config=config,
            guidance='Use best practices'
        )
        
        assert len(messages) > 0
        assert any('best practices' in msg['content'].lower() for msg in messages)

    def test_build_message_order(self):
        """Test that system messages are built in correct order."""
        config = ConfigManager()
        at_context = {
            'files': ['app.py'],
            'non_existing': [],
            'directories': []
        }
        user_input = "refactor @app.py and run it"
        
        messages = build_system_messages(
            at_context=at_context,
            user_input=user_input,
            config=config,
            injected_context_parts=['File: app.py'],
            target_file='output.py',
            session_context='Session info',
            guidance='Guidance text'
        )
        
        # Should have multiple messages
        assert len(messages) >= 4
        
        # Extract content for easier testing
        contents = [msg['content'] for msg in messages]
        
        # File context should come first
        assert any('File: app.py' in c for c in contents[:2])
        
        # Guidance should come last
        assert 'Guidance text' in contents[-1]
