"""
Session Manager for handling context persistence across prompts.

This module provides session management functionality that allows
maintaining conversation context across multiple prompts through
history-based context injection and Redis-based persistence.
"""

import uuid
import os
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from datetime import datetime
import httpx

from src.sentry_config import capture_exception
from src.session.exceptions import WorkingDirectoryMismatchError

if TYPE_CHECKING:
    from src.session.title_generator import SessionTitleGenerator


class SessionManager:
    """
    Manages user sessions with context persistence.

    In a session, all prompts and responses are tracked and injected
    as conversation history context. Without a session, prompts are
    context-independent.

    Sessions can be saved to Redis for persistence and restored later.
    """

    def __init__(self, redis_api_url: Optional[str] = None, title_generator: Optional["SessionTitleGenerator"] = None):
        """
        Initialize the session manager.

        Args:
            redis_api_url: URL for Redis API service. If None, uses environment variable.
            title_generator: Optional SessionTitleGenerator instance for auto-generating titles.
        """
        self.active_session: Optional[str] = None
        self.session_history: List[Dict[str, Any]] = []
        self.session_start_time: Optional[datetime] = None
        self.session_metadata: Dict[str, Any] = {}
        self.session_title: Optional[str] = None
        self._title_generated: bool = False
        self.session_working_dir: Optional[str] = None

        # Title generator for automatic title generation
        self._title_generator = title_generator

        # Redis API URL for persistence (no TTL)
        self.redis_api_url = redis_api_url or os.getenv("REDIS_API_URL", "http://localhost:17000")
        self._session_key_prefix = "cli:session:"

    def set_title_generator(self, title_generator: "SessionTitleGenerator") -> None:
        """
        Set the title generator for automatic title generation.

        Args:
            title_generator: SessionTitleGenerator instance
        """
        self._title_generator = title_generator

    def start_session(self, metadata: Optional[Dict[str, Any]] = None, working_dir: Optional[str] = None) -> str:
        """
        Start a new session.

        Args:
            metadata: Optional metadata to attach to the session
            working_dir: Working directory for the session. If None, uses current directory.

        Returns:
            The session ID (UUID)
        """
        self.active_session = str(uuid.uuid4())
        self.session_history = []
        self.session_start_time = datetime.now()
        self.session_metadata = metadata or {}
        self.session_title = None
        self._title_generated = False
        self.session_working_dir = working_dir or os.getcwd()

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
            "title": self.session_title,
            "start_time": self.session_start_time.isoformat(),
            "duration_seconds": duration,
            "num_interactions": num_interactions,
            "metadata": self.session_metadata,
            "working_dir": self.session_working_dir
        }

        # Clear session state
        self.active_session = None
        self.session_history = []
        self.session_start_time = None
        self.session_metadata = {}
        self.session_title = None
        self._title_generated = False
        self.session_working_dir = None

        print(f"✅ Session ended (started at {start_time_str}, {num_interactions} interactions)")
        return summary

    def is_active(self) -> bool:
        """Check if a session is currently active."""
        return self.active_session is not None

    def add_interaction(self, prompt: str, response: str,
                       metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a prompt-response interaction to the session history.

        After the first interaction, automatically generates a session title
        using tinyollama if a title generator is configured.

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

        # Generate title after first interaction if not already generated
        if len(self.session_history) == 1 and not self._title_generated:
            self._generate_title(prompt)

    def _generate_title(self, first_prompt: str) -> None:
        """
        Generate a title for the session based on the first prompt.

        This is called automatically after the first interaction.

        Args:
            first_prompt: The first user prompt
        """
        if self._title_generator is None:
            return

        try:
            title = self._title_generator.generate_title(first_prompt)
            if title:
                self.session_title = title
                self._title_generated = True
                print(f"📝 Session title: {title}")
        except Exception as e:
            # Title generation is non-critical, don't fail the interaction
            capture_exception(e)

    def set_title(self, title: str) -> None:
        """
        Manually set the session title.

        Args:
            title: The session title
        """
        if self.active_session:
            self.session_title = title
            self._title_generated = True

    def get_title(self) -> Optional[str]:
        """Get the current session title."""
        return self.session_title

    def get_session_context(self, max_interactions: Optional[int] = None) -> str:
        """
        Get the full session context as a formatted string.

        Args:
            max_interactions: Maximum number of recent interactions to include.
                            If None, includes all interactions.

        Returns:
            Formatted context string with conversation history and stored files
        """
        import sys
        print(f"\n[DEBUG] get_session_context() called, active: {self.active_session}", file=sys.stderr)
        if not self.active_session:
            return ""

        context_parts = []

        # First, add stored files/directories from Redis context
        try:
            import requests
            print(f"[DEBUG] Querying Redis for session: {self.active_session[:16]}...", file=sys.stderr)
            response = requests.get(
                f"{self.redis_api_url}/context/list",
                params={"session_id": self.active_session},
                timeout=5
            )
            print(f"[DEBUG] Redis response status: {response.status_code}", file=sys.stderr)

            if response.status_code == 200:
                data = response.json()
                contexts = data.get('contexts', [])
                print(f"[DEBUG] Found {len(contexts)} contexts in Redis", file=sys.stderr)

                if contexts:
                    context_parts.append(f"[Session Context - {len(contexts)} stored file(s)/directory(s)]")

                    for ctx in contexts:
                        path = ctx.get('path', 'Unknown')
                        context_type = ctx.get('context_type', 'unknown')
                        print(f"[DEBUG] Retrieving content for: {path}", file=sys.stderr)

                        # Retrieve full content from Redis
                        try:
                            get_response = requests.get(
                                f"{self.redis_api_url}/context/get",
                                params={
                                    "session_id": self.active_session,
                                    "path": path
                                },
                                timeout=5
                            )

                            if get_response.status_code == 200:
                                content_data = get_response.json()
                                if content_data.get('status') == 'success':
                                    context_obj = content_data.get('context', {})
                                    content = context_obj.get('content', '')
                                    print(f"[DEBUG] Retrieved content length: {len(content)}", file=sys.stderr)
                                    if content:
                                        context_parts.append(f"\n--- {context_type.capitalize()}: {path} ---")
                                        context_parts.append(content)
                        except Exception as e:
                            # Skip this file if retrieval fails
                            print(f"[DEBUG] Error retrieving {path}: {e}", file=sys.stderr)
                            pass

                    context_parts.append("\n")
        except Exception as e:
            # Silently skip if Redis context retrieval fails
            print(f"[DEBUG] Error in Redis context retrieval: {e}", file=sys.stderr)
            pass

        # Then, add conversation history
        if self.session_history:
            history = self.session_history
            if max_interactions:
                history = history[-max_interactions:]

            context_parts.append(f"[Session Context - {len(history)} previous interactions]")

            for i, interaction in enumerate(history, 1):
                context_parts.append(f"\nInteraction {i}:")
                context_parts.append(f"User: {interaction['prompt']}")
                # Truncate long responses for context
                response = interaction['response']
                if len(response) > 500:
                    response = response[:500] + "..."
                context_parts.append(f"Assistant: {response}")

        if context_parts:
            context_parts.append("\n[Current prompt follows]")
            result = "\n".join(context_parts)
            print(f"[DEBUG] Returning context with length: {len(result)}", file=sys.stderr)
            return result

        print("[DEBUG] No context parts to return", file=sys.stderr)
        return ""

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

    def get_working_dir(self) -> Optional[str]:
        """Get the current session working directory, or None if no active session."""
        return self.session_working_dir

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
            "title": self.session_title,
            "active": True,
            "start_time": self.session_start_time.isoformat(),
            "duration_seconds": duration,
            "num_interactions": len(self.session_history),
            "metadata": self.session_metadata,
            "working_dir": self.session_working_dir
        }

    # ========================================================================
    # REDIS PERSISTENCE METHODS
    # ========================================================================

    def save_to_redis(self) -> bool:
        """
        Save the current session to Redis (no TTL - persists until deleted).

        The session is saved with its working directory, which is required
        when restoring the session.

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.active_session:
            return False

        try:
            session_data = {
                "session_id": self.active_session,
                "title": self.session_title,
                "history": self.session_history,
                "start_time": self.session_start_time.isoformat() if self.session_start_time else None,
                "metadata": self.session_metadata,
                "saved_at": datetime.now().isoformat(),
                "working_dir": self.session_working_dir
            }

            # Use Redis directly (no API, direct connection)
            # Store as JSON with no TTL
            key = f"{self._session_key_prefix}{self.active_session}"

            with httpx.Client(timeout=10.0) as client:
                # Store session data
                response = client.post(
                    f"{self.redis_api_url}/session/store",
                    json={
                        "key": key,
                        "data": session_data
                    }
                )

                if response.status_code == 200:
                    return True
                else:
                    return False

        except Exception as e:
            capture_exception(e)
            return False

    def restore_from_redis(self, session_id: str, current_working_dir: Optional[str] = None) -> bool:
        """
        Restore a session from Redis by session ID.

        Sessions can only be restored if the current working directory matches
        the working directory stored with the session.

        Args:
            session_id: The session ID to restore
            current_working_dir: Current working directory. If None, uses os.getcwd()

        Returns:
            True if restored successfully, False otherwise

        Raises:
            WorkingDirectoryMismatchError: If current directory doesn't match session's directory
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

                    # Check working directory match
                    stored_working_dir = session_data.get("working_dir")
                    actual_current_dir = current_working_dir or os.getcwd()

                    if stored_working_dir and stored_working_dir != actual_current_dir:
                        raise WorkingDirectoryMismatchError(stored_working_dir, actual_current_dir)

                    # Restore session state
                    self.active_session = session_data["session_id"]
                    self.session_title = session_data.get("title")
                    self.session_history = session_data["history"]
                    self.session_metadata = session_data.get("metadata", {})
                    self._title_generated = self.session_title is not None
                    self.session_working_dir = stored_working_dir or actual_current_dir

                    # Parse start time
                    start_time_str = session_data.get("start_time")
                    if start_time_str:
                        self.session_start_time = datetime.fromisoformat(start_time_str)
                    else:
                        self.session_start_time = datetime.now()

                    num_interactions = len(self.session_history)
                    title_info = f" - {self.session_title}" if self.session_title else ""
                    print(f"✅ Session restored: {session_id}{title_info} ({num_interactions} interactions)")
                    return True
                else:
                    print(f"⚠️  Session not found: {session_id}")
                    return False

        except WorkingDirectoryMismatchError:
            raise  # Re-raise to let caller handle it
        except Exception as e:
            capture_exception(e)
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
            capture_exception(e)
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
            capture_exception(e)
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
            capture_exception(e)
            print(f"❌ Error clearing sessions: {e}")
            return 0
