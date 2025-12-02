"""Session-related exceptions."""


class WorkingDirectoryMismatchError(Exception):
    """
    Raised when attempting to restore a session from a different working directory.

    Sessions are bound to the working directory they were created in.
    Restoring a session from a different directory is not allowed.
    """

    def __init__(self, stored_dir: str, current_dir: str):
        """
        Initialize the exception.

        Args:
            stored_dir: The working directory stored with the session
            current_dir: The current working directory
        """
        self.stored_dir = stored_dir
        self.current_dir = current_dir
        super().__init__(
            f"Cannot restore session: working directory mismatch. "
            f"Session was created in '{stored_dir}', but current directory is '{current_dir}'"
        )
