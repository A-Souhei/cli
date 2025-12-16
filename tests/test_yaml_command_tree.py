"""Tests for YAML-based command tree loading."""

import pytest
from pathlib import Path
from src.file_completer import SlashCommandCompleter, _load_command_tree_from_yaml


class TestYamlCommandTree:
    """Test YAML command tree loading functionality."""

    def test_yaml_file_exists(self):
        """Test that command_tree.yaml exists in project root."""
        yaml_path = Path(__file__).parent.parent / "command_tree.yaml"
        assert yaml_path.exists(), f"command_tree.yaml not found at {yaml_path}"

    def test_yaml_loads_successfully(self):
        """Test that YAML file can be loaded without errors."""
        tree = _load_command_tree_from_yaml()
        assert isinstance(tree, dict)
        assert len(tree) > 0

    def test_yaml_structure_format(self):
        """Test that YAML is converted to correct internal format."""
        tree = _load_command_tree_from_yaml()
        
        # Each entry should be a tuple of (description, subcommands_dict_or_None)
        for cmd_name, cmd_data in tree.items():
            assert isinstance(cmd_data, tuple)
            assert len(cmd_data) == 2
            description, subcommands = cmd_data
            assert isinstance(description, str)
            assert subcommands is None or isinstance(subcommands, dict)

    def test_yaml_has_expected_root_commands(self):
        """Test that YAML contains expected root commands."""
        tree = _load_command_tree_from_yaml()
        
        expected_commands = ['help', 'exit', 'quit', 'clear', 'models', 'switch',
                           'session', 'context', 'model', 'make', 'execute']
        
        for cmd in expected_commands:
            assert cmd in tree, f"Expected command '{cmd}' not found in tree"

    def test_yaml_nested_structure(self):
        """Test that nested commands are properly loaded."""
        tree = _load_command_tree_from_yaml()
        
        # Test /context add structure
        assert 'context' in tree
        context_desc, context_subs = tree['context']
        assert context_subs is not None
        assert 'add' in context_subs
        
        add_desc, add_subs = context_subs['add']
        assert add_subs is not None
        assert 'ALL' in add_subs
        assert 'TODO_LIST' in add_subs

    def test_yaml_deep_nesting(self):
        """Test deeply nested commands (4+ levels)."""
        tree = _load_command_tree_from_yaml()
        
        # Test /model general add <url> <model_name> structure
        assert 'model' in tree
        model_desc, model_subs = tree['model']
        assert model_subs is not None
        
        assert 'general' in model_subs
        general_desc, general_subs = model_subs['general']
        assert general_subs is not None
        
        assert 'add' in general_subs
        add_desc, add_subs = general_subs['add']
        assert add_subs is not None
        
        assert '<url>' in add_subs
        url_desc, url_subs = add_subs['<url>']
        assert url_subs is not None
        
        assert '<model_name>' in url_subs

    def test_completer_uses_yaml(self):
        """Test that SlashCommandCompleter loads from YAML."""
        completer = SlashCommandCompleter()
        tree = completer.COMMAND_TREE
        
        # Should have same commands as direct YAML load
        yaml_tree = _load_command_tree_from_yaml()
        assert len(tree) == len(yaml_tree)
        assert set(tree.keys()) == set(yaml_tree.keys())

    def test_yaml_cache_is_used(self):
        """Test that command tree is cached after first load."""
        # Clear cache
        SlashCommandCompleter._command_tree_cache = None
        
        # First load
        completer1 = SlashCommandCompleter()
        tree1 = completer1.COMMAND_TREE
        
        # Second load should use cache
        completer2 = SlashCommandCompleter()
        tree2 = completer2.COMMAND_TREE
        
        # Should be the same object (cached)
        assert tree1 is tree2

    def test_fallback_on_yaml_error(self):
        """Test that fallback tree is used if YAML fails to load."""
        # Clear cache
        SlashCommandCompleter._command_tree_cache = None
        
        # Try loading with invalid path
        with pytest.raises(FileNotFoundError):
            _load_command_tree_from_yaml(Path("/nonexistent/path.yaml"))
        
        # Completer should still work with fallback
        completer = SlashCommandCompleter()
        # Force reload with bad path to trigger fallback
        SlashCommandCompleter._command_tree_cache = None
        
        # Mock the load to raise an error
        import src.file_completer as fc
        original_load = fc._load_command_tree_from_yaml
        
        def mock_load_error(path=None):
            raise FileNotFoundError("Test error")
        
        fc._load_command_tree_from_yaml = mock_load_error
        try:
            tree = SlashCommandCompleter._get_command_tree()
            # Should have fallback commands
            assert 'help' in tree
            assert 'exit' in tree
            assert len(tree) > 0  # Fallback should have some commands
        finally:
            # Restore original function
            fc._load_command_tree_from_yaml = original_load
            # Clear cache for other tests
            SlashCommandCompleter._command_tree_cache = None

    def test_yaml_descriptions_are_meaningful(self):
        """Test that all commands have non-empty descriptions."""
        tree = _load_command_tree_from_yaml()
        
        def check_descriptions(subtree, path=""):
            for cmd_name, (description, subcommands) in subtree.items():
                full_path = f"{path}/{cmd_name}" if path else cmd_name
                assert len(description) > 0, f"Empty description for command: {full_path}"
                assert len(description) < 200, f"Description too long for: {full_path}"
                
                if subcommands:
                    check_descriptions(subcommands, full_path)
        
        check_descriptions(tree)

    def test_yaml_leaf_commands_have_null_subcommands(self):
        """Test that leaf commands properly have None subcommands."""
        tree = _load_command_tree_from_yaml()
        
        # Leaf commands should have None as subcommands
        assert 'help' in tree
        help_desc, help_subs = tree['help']
        assert help_subs is None
        
        assert 'clear' in tree
        clear_desc, clear_subs = tree['clear']
        assert clear_subs is None
