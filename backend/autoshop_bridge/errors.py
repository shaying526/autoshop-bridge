"""Errors safe to report through the CLI."""


class BridgeError(Exception):
    """Invalid input, unsupported format, or rejected operation."""


class ConflictError(BridgeError):
    """The target changed relative to the expected baseline."""
