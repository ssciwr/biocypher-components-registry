"""Credential-safe persistence setup errors shared by entry points."""


class DatabaseSetupError(RuntimeError):
    """The database could not be prepared before adapter processing began."""
