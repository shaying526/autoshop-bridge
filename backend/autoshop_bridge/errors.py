"""Errors safe to report through the CLI."""


class BridgeError(Exception):
    """Invalid input, unsupported format, or rejected operation."""


class ConflictError(BridgeError):
    """The target changed relative to the expected baseline."""


class FormatRejection(BridgeError):
    """Evidence-bounded format refusal with optional, bounded diagnostic fields.

    Context contains caller-selected JSON-compatible metadata, never native
    buffers or complete source. Workflow layers may add target identity without
    replacing the member-level evidence supplied by a format parser.
    """

    def __init__(self, message, *, code="format_rejected", context=None):
        super().__init__(message)
        self.code = code
        self.context = dict(context) if context is not None else {}
