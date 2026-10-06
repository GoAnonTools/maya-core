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
