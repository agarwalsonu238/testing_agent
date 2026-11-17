"""Domain errors raised by services and mapped to HTTP responses in `create_app()`."""


class DomainError(Exception):
    """Base class. `str(error)` is safe to show to the caller."""


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    """The request is valid but the current state doesn't allow it (e.g. a run is active)."""


class PreconditionError(DomainError):
    """Local setup isn't ready for this action (e.g. an API key is set, no app repo configured)."""


class BlockedError(DomainError):
    """A run can't finish for a reason outside the code under test. Ends the run as BLOCKED."""
