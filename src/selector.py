"""Interactive selector with arrow key navigation."""

from typing import List, Optional
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style


class InteractiveSelector:
    """Interactive menu selector with arrow key navigation."""

    def __init__(self, title: str, choices: List[str], current: Optional[str] = None):
        """
        Initialize the selector.

        Args:
            title: Title to display above the menu
            choices: List of options to select from
            current: Current selected option (will be highlighted)
        """
        self.title = title
        self.choices = choices
        self.current = current
        self.selected_index = 0

        # Set initial index to current item if provided
        if current and current in choices:
            self.selected_index = choices.index(current)

        self.result = None

    def _get_formatted_text(self) -> FormattedText:
        """Generate formatted text for the menu."""
        result = [
            ('class:title', f"{self.title}\n"),
            ('', '\n'),
        ]

        for i, choice in enumerate(self.choices):
            if i == self.selected_index:
                # Selected item - cyan with arrow
                prefix = '▶ '
                style = 'class:selected'
            elif choice == self.current:
                # Current item (if not selected) - show marker
                prefix = '  '
                style = 'class:current'
            else:
                # Regular item
                prefix = '  '
                style = 'class:item'

            result.append((style, f"{prefix}{choice}\n"))

        result.append(('', '\n'))
        result.append(('class:hint', 'Use ↑/↓ arrows to navigate, Enter to select, Esc to cancel'))

        return FormattedText(result)

    def _create_layout(self) -> Layout:
        """Create the layout for the selector."""
        control = FormattedTextControl(
            text=self._get_formatted_text,
            focusable=True,
        )

        window = Window(
            content=control,
            height=len(self.choices) + 5,
        )

        return Layout(HSplit([window]))

    def _create_key_bindings(self) -> KeyBindings:
        """Create key bindings for the selector."""
        kb = KeyBindings()

        @kb.add('up')
        def move_up(event):
            """Move selection up."""
            self.selected_index = (self.selected_index - 1) % len(self.choices)

        @kb.add('down')
        def move_down(event):
            """Move selection down."""
            self.selected_index = (self.selected_index + 1) % len(self.choices)

        @kb.add('enter')
        def select(event):
            """Select current item."""
            self.result = self.choices[self.selected_index]
            event.app.exit()

        @kb.add('escape')
        @kb.add('c-c')
        def cancel(event):
            """Cancel selection."""
            self.result = None
            event.app.exit()

        return kb

    def show(self) -> Optional[str]:
        """
        Show the selector and return the selected choice.

        Returns:
            Selected choice or None if cancelled
        """
        # Define custom styles
        style = Style.from_dict({
            'title': 'bold cyan',
            'selected': 'bold green',
            'current': 'cyan',
            'item': '',
            'hint': 'dim',
        })

        # Create the application
        app = Application(
            layout=self._create_layout(),
            key_bindings=self._create_key_bindings(),
            style=style,
            full_screen=False,
            mouse_support=True,
        )

        # Run the application
        app.run()

        return self.result
