"""Typed failure states for Hermes transport and execution."""


class HermesError(RuntimeError):
    """Base class for expected Hermes boundary failures."""


class HermesUnavailableError(HermesError):
    """Hermes is not configured, healthy, or available."""


class HermesNetworkError(HermesError):
    """A network or protocol operation failed."""


class HermesTimeoutError(HermesNetworkError):
    """A Hermes operation exceeded its configured timeout."""


class HermesPartialStreamError(HermesNetworkError):
    """The event stream disconnected before a terminal event."""


class HermesUnknownTerminalState(HermesError):
    """The stream ended without a recognized terminal event."""


class HermesPersistenceError(HermesError):
    """Run mapping persistence or recovery failed."""


def user_friendly_message(error: HermesError) -> str:
    """Return a concise message for an expected Hermes boundary failure."""
    if isinstance(error, HermesUnavailableError):
        return "Hermes is unavailable. Local execution remains available."
    if isinstance(error, HermesTimeoutError):
        return "Hermes took too long to respond. Please try again."
    if isinstance(error, HermesPartialStreamError):
        return "Hermes disconnected before the task finished."
    if isinstance(error, HermesUnknownTerminalState):
        return "Hermes ended without reporting a final result."
    if isinstance(error, HermesNetworkError):
        return "Maya could not reach Hermes. Please check the local service."
    if isinstance(error, HermesPersistenceError):
        return "Maya could not save Hermes task state."
    return "Hermes could not complete the task."
