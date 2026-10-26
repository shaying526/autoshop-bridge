"""Strict read-only recognition of the observed V4.11 empty table profile.

Only the fixed CArchive row descriptors are recognized. Header bytes remain
opaque; there is no serializer or general empty-container inference here.
"""

MAGIC = b"AutoShop"
_ROWS = bytes.fromhex(
    "00000000010000000000000000000001800100000001000000000000000000000180"
    "020000000100000000000000000000018002000000010000000000000000000000000000"
)
DECLARATION_TAIL = b"\x04\x00\xff\xff\x01\x00\x08\x00CLVTItem" + _ROWS
IMPLICIT_TAIL = b"\x04\x00\x01\x80" + _ROWS


def count_offset(raw):
    """Return an observed zero declaration count, otherwise refuse recognition."""
    if (not isinstance(raw, bytes) or not raw.startswith(MAGIC)
            or not len(DECLARATION_TAIL) + len(MAGIC) <= len(raw) <= 4096
            or not raw.endswith(DECLARATION_TAIL)):
        return None
    header = raw[:-len(DECLARATION_TAIL)]
    if MAGIC in header[len(MAGIC):]:
        return None
    return len(raw) - 4


def instance_segment(raw):
    """Two empty tables share the same opaque header and CArchive class state."""
    boundary = raw.find(MAGIC, len(MAGIC))
    if boundary < 0:
        return None
    primary = raw[:boundary]
    start = count_offset(primary)
    if start is None:
        return None
    header = primary[:-len(DECLARATION_TAIL)]
    if raw[boundary:] != header + IMPLICIT_TAIL:
        return None
    return start, boundary
