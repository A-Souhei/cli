"""Tests for nested command completions in SlashCommandCompleter."""

from prompt_toolkit.document import Document
from src.file_completer import SlashCommandCompleter


class TestNestedCompletions:
    """Test nested command completion functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.completer = SlashCommandCompleter()

    def test_root_level_completions(self):
        """Test that root level commands are shown when typing /."""
        document = Document(text='/', cursor_position=1)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show all root level commands
        assert len(completions) > 0
        
        # Check for some expected root commands
        completion_texts = [c.text for c in completions]
        assert '/help' in completion_texts
        assert '/session' in completion_texts
        assert '/context' in completion_texts
        assert '/model' in completion_texts

    def test_context_subcommands(self):
        """Test that /context shows subcommands."""
        document = Document(text='/context ', cursor_position=9)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show context subcommands
        completion_texts = [c.text for c in completions]
        assert '/context add' in completion_texts
        assert '/context show' in completion_texts
        assert '/context clear' in completion_texts
        assert '/context metrics' in completion_texts
        assert '/context load' in completion_texts
        assert '/context save' in completion_texts

    def test_context_add_options(self):
        """Test that /context add shows options."""
        document = Document(text='/context add ', cursor_position=13)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show context add options
        completion_texts = [c.text for c in completions]
        assert '/context add @file' in completion_texts
        assert '/context add @directory' in completion_texts
        assert '/context add ALL' in completion_texts
        assert '/context add ALL_TOOLS' in completion_texts
        assert '/context add TODO_LIST' in completion_texts
        assert '/context add MAKE_LIST' in completion_texts

    def test_session_subcommands(self):
        """Test that /session shows subcommands."""
        document = Document(text='/session ', cursor_position=9)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show session subcommands
        completion_texts = [c.text for c in completions]
        assert '/session start' in completion_texts
        assert '/session end' in completion_texts
        assert '/session info' in completion_texts
        assert '/session list' in completion_texts
        assert '/session restore' in completion_texts
        assert '/session delete' in completion_texts
        assert '/session clear' in completion_texts

    def test_model_subcommands(self):
        """Test that /model shows subcommands."""
        document = Document(text='/model ', cursor_position=7)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show model subcommands
        completion_texts = [c.text for c in completions]
        assert '/model status' in completion_texts
        assert '/model list' in completion_texts
        assert '/model general' in completion_texts
        assert '/model coder' in completion_texts
        assert '/model embedding' in completion_texts
        assert '/model check' in completion_texts

    def test_partial_matching(self):
        """Test that partial command input shows matching completions."""
        document = Document(text='/con', cursor_position=4)
        completions = list(self.completer.get_completions(document, None))
        
        # Should match context
        completion_texts = [c.text for c in completions]
        assert '/context' in completion_texts

    def test_nested_level_partial_matching(self):
        """Test partial matching at nested levels."""
        document = Document(text='/context ad', cursor_position=11)
        completions = list(self.completer.get_completions(document, None))
        
        # Should match 'add'
        completion_texts = [c.text for c in completions]
        assert '/context add' in completion_texts

    def test_make_map_commands(self):
        """Test that /make map shows subcommands."""
        document = Document(text='/make map ', cursor_position=10)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show make map subcommands
        completion_texts = [c.text for c in completions]
        assert '/make map generate' in completion_texts
        assert '/make map load' in completion_texts
        assert '/make map update' in completion_texts

    def test_completion_descriptions(self):
        """Test that completions have descriptions."""
        document = Document(text='/', cursor_position=1)
        completions = list(self.completer.get_completions(document, None))
        
        # All completions should have display_meta (description)
        for completion in completions:
            assert completion.display_meta is not None
            assert len(completion.display_meta) > 0

    def test_ignore_commands(self):
        """Test that /ignore shows subcommands."""
        document = Document(text='/ignore ', cursor_position=8)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show ignore subcommands
        completion_texts = [c.text for c in completions]
        assert '/ignore create' in completion_texts
        assert '/ignore add' in completion_texts

    def test_execute_commands(self):
        """Test that /execute shows options."""
        document = Document(text='/execute ', cursor_position=9)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show execute options
        completion_texts = [c.text for c in completions]
        assert '/execute TODO_LIST' in completion_texts
        assert '/execute MAKE_LIST' in completion_texts
        assert '/execute @path' in completion_texts

    def test_no_completions_after_leaf(self):
        """Test that no completions are shown after a leaf command."""
        # 'clear' is a leaf command with no subcommands
        document = Document(text='/clear ', cursor_position=7)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show no completions since clear is a leaf
        assert len(completions) == 0

    def test_context_load_options(self):
        """Test that /context load shows TODO_LIST and MAKE_LIST."""
        document = Document(text='/context load ', cursor_position=14)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show load options
        completion_texts = [c.text for c in completions]
        assert '/context load TODO_LIST' in completion_texts
        assert '/context load MAKE_LIST' in completion_texts

    def test_context_save_options(self):
        """Test that /context save shows TODO_LIST and MAKE_LIST."""
        document = Document(text='/context save ', cursor_position=14)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show save options
        completion_texts = [c.text for c in completions]
        assert '/context save TODO_LIST' in completion_texts
        assert '/context save MAKE_LIST' in completion_texts

    def test_model_general_subcommands(self):
        """Test that /model general shows subcommands."""
        document = Document(text='/model general ', cursor_position=15)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show general model subcommands
        completion_texts = [c.text for c in completions]
        assert '/model general list' in completion_texts
        assert '/model general add' in completion_texts
        assert '/model general use' in completion_texts
        assert '/model general remove' in completion_texts

    def test_repomap_commands(self):
        """Test that /repomap shows subcommands."""
        document = Document(text='/repomap ', cursor_position=9)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show repomap subcommands
        completion_texts = [c.text for c in completions]
        assert '/repomap create' in completion_texts
        assert '/repomap load' in completion_texts
        assert '/repomap update' in completion_texts

    def test_datamap_commands(self):
        """Test that /datamap shows subcommands."""
        document = Document(text='/datamap ', cursor_position=9)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show datamap subcommands
        completion_texts = [c.text for c in completions]
        assert '/datamap create' in completion_texts
        assert '/datamap load' in completion_texts
        assert '/datamap update' in completion_texts

    def test_placeholder_shows_in_completion(self):
        """Test that placeholders are shown in completions."""
        # /session restore should show <id> placeholder
        document = Document(text='/session restore ', cursor_position=17)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show the placeholder
        completion_texts = [c.text for c in completions]
        assert any('<id>' in text for text in completion_texts)

    def test_placeholder_with_subcommands(self):
        """Test that placeholders with subcommands navigate correctly."""
        # /model general add <url> should show <model_name> placeholder
        document = Document(text='/model general add https://ollama.ai ', cursor_position=37)
        completions = list(self.completer.get_completions(document, None))
        
        # Should show the next level placeholder
        completion_texts = [c.text for c in completions]
        assert any('<model_name>' in text for text in completion_texts)
