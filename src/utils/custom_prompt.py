"""Custom prompt functionality for the CLI with visual enhancements."""

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import Layout, HSplit, Window, FloatContainer, Float
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings


def custom_prompt_with_lines(console, history=None, completer=None):
    """
    Custom prompt that displays horizontal lines above and below the input area.
    Both lines are visible while typing.

    Args:
        console: Rich console instance for getting terminal width
        history: Optional FileHistory instance for command history
        completer: Optional completer instance for autocompletion

    Returns:
        str: The user's input text
    """
    # Variable to store the result
    result_text = {'value': ''}

    # Accept handler that captures input and exits
    def accept_handler(buff):
        result_text['value'] = buff.text
        # Get the application and exit
        from prompt_toolkit.application import get_app
        get_app().exit()
        return True

    # Create a buffer for the input
    buffer = Buffer(
        multiline=True,  # Enable multi-line input
        history=history,
        completer=completer,
        complete_while_typing=True,
        accept_handler=accept_handler
    )

    # Get console width for the horizontal lines
    line = '─' * console.width

    # Create the layout with three windows stacked vertically
    input_window = Window(
        content=BufferControl(
            buffer=buffer,
            focusable=True,
            focus_on_click=True
        ),
        get_line_prefix=lambda line_number, wrap_count: FormattedText([('ansigreen bold', '▶ ' if line_number == 0 else '  ')]),
        wrap_lines=True,  # Wrap long lines
        height=Dimension(min=1, max=20),  # Start with 1 line, grow up to 20 lines
        dont_extend_height=True  # Don't expand to fill available space
    )

    # For single-line input, just show the bottom line
    # For multi-line, we'll handle it with a simpler approach
    root_container = HSplit([
        # Top horizontal line
        Window(
            content=FormattedTextControl(text=line),
            height=1
        ),
        # Input area with green arrow prompt
        input_window,
        # Bottom line - keep it simple and always one line
        Window(
            content=FormattedTextControl(text=line),
            height=1
        ),
    ])

    # Wrap in FloatContainer to support completion menu
    container = FloatContainer(
        content=root_container,
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(max_height=10)
            )
        ]
    )

    # Create key bindings
    kb = KeyBindings()

    @kb.add('enter')
    def _(event):
        # Enter adds a new line in multi-line mode
        event.current_buffer.insert_text('\n')

    @kb.add('escape', 'enter')  # Alt+Enter submits
    def _(event):
        # Alt+Enter accepts the current input (triggers accept_handler)
        event.current_buffer.validate_and_handle()

    @kb.add('c-j')  # Ctrl+J also submits
    def _(event):
        # Ctrl+J accepts the current input (triggers accept_handler)
        event.current_buffer.validate_and_handle()

    @kb.add('c-c')
    def _(event):
        # Ctrl+C clears the input buffer instead of exiting
        event.current_buffer.text = ''

    @kb.add('c-d')
    def _(event):
        # Ctrl+D returns special marker for exit intent
        # Only exit if buffer is empty, otherwise delete character
        if event.current_buffer.text:
            # If there's text, Ctrl+D deletes the character after cursor
            event.current_buffer.delete()
        else:
            # If buffer is empty, Ctrl+D exits
            result_text['value'] = '__CTRL_D__'
            event.app.exit()

    # Create the application
    app = Application(
        layout=Layout(container),
        key_bindings=kb,
        full_screen=False,
        mouse_support=False  # Disabled to allow terminal text selection
    )

    # Run the application and return the captured input
    app.run()
    return result_text['value']
