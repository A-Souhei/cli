"""
Session Manager for handling context persistence across prompts.

This module provides session management functionality that allows
maintaining conversation context across multiple prompts through
history-based context injection and Redis-based persistence.
"""

import uuid
import json
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
import httpx


class SessionManager:
    """
    Manages user sessions with context persistence.

    In a session, all prompts and responses are tracked and injected
    as conversation history context. Without a session, prompts are
    context-independent.

    Sessions can be saved to Redis for persistence and restored later.
    """

    def __init__(self, redis_api_url: Optional[str] = None):
        """
        Initialize the session manager.

        Args:
            redis_api_url: URL for Redis API service. If None, uses environment variable.
        """
        self.active_session: Optional[str] = None
        self.session_history: List[Dict[str, Any]] = []
        self.session_start_time: Optional[datetime] = None
        self.session_metadata: Dict[str, Any] = {}

        # Redis API URL for persistence (no TTL)
        self.redis_api_url = redis_api_url or os.getenv("REDIS_API_URL", "http://localhost:17000")
        self._session_key_prefix = "cli:session:"

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

        start_time_str = self.session_start_time.strftime("%H:%M:%S")
        print(f"📝 Session started at {start_time_str}")
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
        start_time_str = self.session_start_time.strftime("%H:%M:%S")

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

        print(f"✅ Session ended (started at {start_time_str}, {num_interactions} interactions)")
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

    # ========================================================================
    # REDIS PERSISTENCE METHODS
    # ========================================================================

    def save_to_redis(self) -> bool:
        """
        Save the current session to Redis (no TTL - persists until deleted).

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.active_session:
            print("⚠️  No active session to save.")
            return False

        try:
            session_data = {
                "session_id": self.active_session,
                "history": self.session_history,
                "start_time": self.session_start_time.isoformat() if self.session_start_time else None,
                "metadata": self.session_metadata,
                "saved_at": datetime.now().isoformat()
            }

            # Use Redis directly (no API, direct connection)
            # Store as JSON with no TTL
            key = f"{self._session_key_prefix}{self.active_session}"

            with httpx.Client(timeout=10.0) as client:
                # Check if Redis API has a generic set endpoint
                # For now, we'll use a simple approach with redis-py if available
                # Otherwise, store via file or implement custom endpoint

                # Store session data
                response = client.post(
                    f"{self.redis_api_url}/session/store",
                    json={
                        "key": key,
                        "data": session_data
                    }
                )

                if response.status_code == 200:
                    print(f"💾 Session saved: {self.active_session}")
                    return True
                else:
                    print(f"⚠️  Failed to save session: {response.text}")
                    return False

        except Exception as e:
            print(f"❌ Error saving session: {e}")
            return False

    def restore_from_redis(self, session_id: str) -> bool:
        """
        Restore a session from Redis by session ID.

        Args:
            session_id: The session ID to restore

        Returns:
            True if restored successfully, False otherwise
        """
        try:
            key = f"{self._session_key_prefix}{session_id}"

            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{self.redis_api_url}/session/retrieve",
                    params={"key": key}
                )

                if response.status_code == 200:
                    session_data = response.json()

                    # Restore session state
                    self.active_session = session_data["session_id"]
                    self.session_history = session_data["history"]
                    self.session_metadata = session_data.get("metadata", {})

                    # Parse start time
                    start_time_str = session_data.get("start_time")
                    if start_time_str:
                        self.session_start_time = datetime.fromisoformat(start_time_str)
                    else:
                        self.session_start_time = datetime.now()

                    num_interactions = len(self.session_history)
                    print(f"✅ Session restored: {session_id} ({num_interactions} interactions)")
                    return True
                else:
                    print(f"⚠️  Session not found: {session_id}")
                    return False

        except Exception as e:
            print(f"❌ Error restoring session: {e}")
            return False

    def list_saved_sessions(self) -> List[Dict[str, Any]]:
        """
        List all saved sessions in Redis.

        Returns:
            List of session summaries
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{self.redis_api_url}/session/list",
                    params={"prefix": self._session_key_prefix}
                )

                if response.status_code == 200:
                    sessions = response.json().get("sessions", [])
                    return sessions
                else:
                    print(f"⚠️  Failed to list sessions: {response.text}")
                    return []

        except Exception as e:
            print(f"❌ Error listing sessions: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a saved session from Redis.

        Args:
            session_id: The session ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            key = f"{self._session_key_prefix}{session_id}"

            with httpx.Client(timeout=10.0) as client:
                response = client.delete(
                    f"{self.redis_api_url}/session/delete",
                    params={"key": key}
                )

                if response.status_code == 200:
                    print(f"🗑️  Session deleted: {session_id}")
                    return True
                else:
                    print(f"⚠️  Failed to delete session: {response.text}")
                    return False

        except Exception as e:
            print(f"❌ Error deleting session: {e}")
            return False

    def clear_all_sessions(self) -> int:
        """
        Clear all saved sessions from Redis.

        Returns:
            Number of sessions deleted
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.delete(
                    f"{self.redis_api_url}/session/clear",
                    params={"prefix": self._session_key_prefix}
                )

                if response.status_code == 200:
                    count = response.json().get("deleted_count", 0)
                    print(f"🗑️  Cleared {count} saved sessions")
                    return count
                else:
                    print(f"⚠️  Failed to clear sessions: {response.text}")
                    return 0

        except Exception as e:
            print(f"❌ Error clearing sessions: {e}")
            return 0
