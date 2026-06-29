class ConfigurationError(Exception):
    """Raised when application or database configuration is invalid or missing."""


class UnknownDatabaseError(Exception):
    """Raised when a requested database name is not in configuration."""
