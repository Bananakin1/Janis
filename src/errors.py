"""Shared Janis error types."""


class JanisError(Exception):
    """Base error for the Janis application."""


class ValidationFailure(JanisError):
    """Raised when user input or tool arguments fail validation."""


class BackendError(JanisError):
    """Raised when a backend integration fails."""


class BackendUnavailableError(BackendError):
    """Raised when a backend dependency is not available."""


class ToolExecutionError(JanisError):
    """Raised when a tool cannot complete."""


class ProviderError(JanisError):
    """Raised when the LLM provider cannot complete a request."""


class ConfirmationRequiredError(ToolExecutionError):
    """Raised when a destructive action requires explicit confirmation."""
