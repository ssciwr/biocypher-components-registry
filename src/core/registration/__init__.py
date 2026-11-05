"""Shared synchronous registration services."""

from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.models import StoredRegistration
from src.core.registration.service import register_adapter, update_adapter
from src.core.registration.store import RegistrationStore

__all__ = [
    "DuplicateRegistrationError",
    "RegistrationStore",
    "StoredRegistration",
    "register_adapter",
    "update_adapter",
]
