"""Public registration API for storing submitted adapter registrations."""

from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.models import RegistrationStatus, StoredRegistration
from src.core.registration.service import finish_registration, submit_registration
from src.core.registration.store import RegistrationStore

__all__ = [
    "DuplicateRegistrationError",
    "RegistrationStatus",
    "RegistrationStore",
    "StoredRegistration",
    "finish_registration",
    "submit_registration",
]
