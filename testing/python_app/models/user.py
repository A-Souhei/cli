"""User model."""

from dataclasses import dataclass
from datetime import datetime
from ..utils import validate_email


@dataclass
class User:
    """User data model."""

    id: int
    name: str
    email: str
    created_at: datetime = None

    def __post_init__(self):
        """Validate user data after initialization."""
        if not validate_email(self.email):
            raise ValueError(f"Invalid email address: {self.email}")

        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Create user from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            email=data['email'],
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        )
