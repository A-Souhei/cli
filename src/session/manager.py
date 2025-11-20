"""
Session Manager for handling context persistence across prompts.

This module provides session management functionality that allows
maintaining conversation context with embedded RAG across multiple prompts.
"""

import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime
import json


class SessionManager:
    """
    Manages user sessions with context persistence.

    In a session, all prompts and responses are tracked and embedded
    for context-aware RAG retrieval. Without a session, prompts are
    context-independent.
    """

    def __init__(self):
        """Initialize the session manager."""
        self.active_session: Optional[str] = None
        self.session_history: List[Dict[str, Any]] = []
        self.session_start_time: Optional[datetime] = None
        self.session_metadata: Dict[str, Any] = {}

    def start_session(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new session.

        Args:
            metadata: Optional metadata to attach to the session

        Returns:
            The session ID (UUID)
        """
        self.active_session = str(uuid.uuid4())
        self.session_history = []
        self.session_start_time = datetime.now()
        self.session_metadata = metadata or {}

        print(f"📝 Session started: {self.active_session[:8]}...")
        return self.active_session

    def end_session(self) -> Optional[Dict[str, Any]]:
        """
        End the current session.

        Returns:
            Session summary with metadata, or None if no active session
        """
        if not self.active_session:
            print("⚠️  No active session to end.")
            return None

        session_id = self.active_session
        duration = (datetime.now() - self.session_start_time).total_seconds()
        num_interactions = len(self.session_history)

        summary = {
            "session_id": session_id,
            "start_time": self.session_start_time.isoformat(),
            "duration_seconds": duration,
            "num_interactions": num_interactions,
            "metadata": self.session_metadata
        }

        # Clear session state
        self.active_session = None
        self.session_history = []
        self.session_start_time = None
        self.session_metadata = {}

        print(f"✅ Session ended: {session_id[:8]}... ({num_interactions} interactions)")
        return summary

    def is_active(self) -> bool:
        """Check if a session is currently active."""
        return self.active_session is not None

    def add_interaction(self, prompt: str, response: str,
                       metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a prompt-response interaction to the session history.

        Args:
            prompt: The user's prompt
            response: The assistant's response
            metadata: Optional metadata (e.g., model used, tokens, etc.)
        """
        if not self.active_session:
            return

        interaction = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response": response,
            "metadata": metadata or {}
        }

        self.session_history.append(interaction)

    def get_session_context(self, max_interactions: Optional[int] = None) -> str:
        """
        Get the full session context as a formatted string.

        Args:
            max_interactions: Maximum number of recent interactions to include.
                            If None, includes all interactions.

        Returns:
            Formatted context string with conversation history
        """
        if not self.active_session or not self.session_history:
            return ""

        history = self.session_history
        if max_interactions:
            history = history[-max_interactions:]

        context_parts = [f"[Session Context - {len(history)} previous interactions]"]

        for i, interaction in enumerate(history, 1):
            context_parts.append(f"\nInteraction {i}:")
            context_parts.append(f"User: {interaction['prompt']}")
            # Truncate long responses for context
            response = interaction['response']
            if len(response) > 500:
                response = response[:500] + "..."
            context_parts.append(f"Assistant: {response}")

        context_parts.append("\n[Current prompt follows]")
        return "\n".join(context_parts)

    def get_session_history(self) -> List[Dict[str, Any]]:
        """
        Get the raw session history.

        Returns:
            List of interaction dictionaries
        """
        return self.session_history.copy()

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID, or None if no active session."""
        return self.active_session

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current session.

        Returns:
            Dictionary with session information, or empty dict if no session
        """
        if not self.active_session:
            return {}

        duration = (datetime.now() - self.session_start_time).total_seconds()

        return {
            "session_id": self.active_session,
            "active": True,
            "start_time": self.session_start_time.isoformat(),
            "duration_seconds": duration,
            "num_interactions": len(self.session_history),
            "metadata": self.session_metadata
        }
