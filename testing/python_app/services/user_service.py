"""User service layer."""

from typing import List, Optional
from ..models import User
import validate_email


class UserService:
    """Service for managing users."""

    def __init__(self):
        """Initialize user service."""
        self.users: List[User] = []
        self._next_id = 1

    def create_user(self, name: str, email: str) -> User:
        """
        Create a new user.

        Args:
            name: User name
            email: User email

        Returns:
            Created user

        Raises:
            ValueError: If email is invalid
        """
        if not validate_email.validate_email(email):
            raise ValueError("Invalid email address")
        user = User(id=self._next_id, name=name, email=email)
        self.users.append(user)
        self._next_id += 1
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User if found, None otherwise
        """
        for user in self.users:
            if user.id == user_id:
                return user
        return None

    def get_all_users(self) -> List[User]:
        """Get all users."""
        return self.users.copy()

    def update_user(self, user_id: int, name: str = None, email: str = None) -> Optional[User]:
        """
        Update user information.

        Args:
            user_id: User ID
            name: New name (optional)
            email: New email (optional)

        Returns:
            Updated user if found, None otherwise
        """
        user = self.get_user(user_id)
        if user:
            if name:
                user.name = name
            if email:
                user.email = email
            return user
        return None

    def delete_user(self, user_id: int) -> bool:
        """
        Delete user by ID.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        user = self.get_user(user_id)
        if user:
            self.users.remove(user)
            return True
        return False

    def search_users(self, query: str) -> List[User]:
        """
        Search users by name or email.

        Args:
            query: Search query

        Returns:
            List of matching users
        """
        query = query.lower()
        return [
            user for user in self.users
            if query in user.name.lower() or query in user.email.lower()
        ]