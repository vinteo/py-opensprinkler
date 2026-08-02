class OpenSprinklerAuthError(Exception):
    """Exception for authentication error."""


class OpenSprinklerConnectionError(Exception):
    """Exception for connection error."""


class OpenSprinklerNoStateError(Exception):
    """Exception for no state."""


class OpenSprinklerApiError(Exception):
    """Exception for an error returned by the API."""


class FirmwareNotSupportedError(Exception):
    """Exception for a feature not supported by the firmware."""
