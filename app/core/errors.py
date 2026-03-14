class EngineError(Exception):
    """Base exception for engine failures."""


class EngineBusyError(EngineError):
    """Raised when another process request is already running."""


class ProcessingTimeoutError(EngineError):
    """Raised when processing exceeds the configured timeout."""


class ProviderUnavailableError(EngineError):
    """Raised when a provider cannot be used."""


class ConfigurationError(EngineError):
    """Raised when required configuration is missing or invalid."""


class InputFileError(EngineError):
    """Raised when the input image path is invalid."""
