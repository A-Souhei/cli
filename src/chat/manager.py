"""Chat manager for managing conversations with the AI."""

from typing import List, Dict


class ChatManager:
    """Manages chat conversations and context."""

    def __init__(self, system_prompt: str, max_context_length: int = 10):
        """
        Initialize the ChatManager.

        Args:
            system_prompt: System prompt to guide the AI
            max_context_length: Maximum number of messages to keep in context
        """
        self.system_prompt = system_prompt
        self.max_context_length = max_context_length
        self.messages: List[Dict[str, str]] = []

        # Add system prompt if provided
        if system_prompt:
            self.messages.append({
                'role': 'system',
                'content': system_prompt
            })

    def add_user_message(self, content: str):
        """Add a user message to the conversation."""
        self.messages.append({
            'role': 'user',
            'content': content
        })
        self._trim_context()

    def add_assistant_message(self, content: str):
        """Add an assistant message to the conversation."""
        self.messages.append({
            'role': 'assistant',
            'content': content
        })
        self._trim_context()

    def get_messages(self) -> List[Dict[str, str]]:
        """Get all messages in the conversation."""
        return self.messages

    def _trim_context(self):
        """Trim the conversation context to max_context_length."""
        # Keep system prompt and limit conversation history
        if len(self.messages) > self.max_context_length + 1:
            # Keep system prompt (first message) and last max_context_length messages
            system_msg = self.messages[0] if self.messages[0]['role'] == 'system' else None
            conversation_msgs = [msg for msg in self.messages if msg['role'] != 'system']

            # Keep only the most recent messages
            conversation_msgs = conversation_msgs[-self.max_context_length:]

            # Reconstruct messages list
            if system_msg:
                self.messages = [system_msg] + conversation_msgs
            else:
                self.messages = conversation_msgs

    def clear_history(self):
        """Clear conversation history but keep system prompt."""
        system_msg = None
        if self.messages and self.messages[0]['role'] == 'system':
            system_msg = self.messages[0]

        self.messages = [system_msg] if system_msg else []

    def print_message(self, role: str, content: str, stream: bool = False):
        """
        Print a message to the console.

        Args:
            role: Message role (user/assistant)
            content: Message content
            stream: Whether to print without newline for streaming
        """
        prefix = "You: " if role == "user" else "AI: "

        if stream:
            print(content, end='', flush=True)
        else:
            print(f"{prefix}{content}")
