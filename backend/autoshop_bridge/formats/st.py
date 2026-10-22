"""Sample-driven ST container recognition, not a full AutoShop parser.

Evidence: 08_data/autoshop_format_probe and the project format study.
Unknown prefix and per-line fields must remain byte-for-byte unchanged.
"""

import struct
from dataclasses import dataclass

from autoshop_bridge.errors import BridgeError

KEY = b"SclSoftware"
PROFILE = "autoshop-st-line-table-v1-experimental"
MAX_NATIVE_SIZE = 16 * 1024 * 1024
# User-reported AutoShop V4.11.0.5 program-body limit; not a table-row limit.
MAX_PROGRAM_LINES = 1000


def decode(payload: bytes) -> bytes:
    return bytes(
        (((value ^ (i & 255)) if i % 2 == 0 else value) - KEY[(i + 1) % len(KEY)]) & 255
        for i, value in enumerate(payload)
    )


def encode(source: bytes) -> bytes:
    return bytes(
        ((value + KEY[(i + 1) % len(KEY)]) & 255) ^ ((i & 255) if i % 2 == 0 else 0)
        for i, value in enumerate(source)
    )


def validate_text(source: bytes) -> None:
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BridgeError("Source must be strict UTF-8.") from exc
    if text.startswith("\ufeff"):
        raise BridgeError("Source must be UTF-8 without BOM.")
    if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        raise BridgeError("Source contains unsupported control characters.")
    if b"\r" in source.replace(b"\r\n", b""):
        raise BridgeError("Lone CR is unsupported; use LF or CRLF.")


def validate_program_edit(source: bytes) -> None:
    """Editor edits need no invented native row metadata; retain body limits."""
    validate_text(source)
    if len(source) > MAX_NATIVE_SIZE:
        raise BridgeError("Source exceeds the supported size limit.")
    if source.count(b"\n") + 1 > MAX_PROGRAM_LINES:
        raise BridgeError("Program body exceeds the 1000-line AutoShop limit.")


@dataclass(frozen=True)
class Container:
    raw: bytes
    length_offset: int
    payload_offset: int
    payload_length: int
    source: bytes
    line_count: int

    @property
    def line_table_count(self):
        return self.line_count

    def rebuild(self, source: bytes) -> bytes:
        validate_text(source)
        if source == self.source:
            return self.raw
        if self.source.count(b"\n") + 1 != self.line_table_count:
            raise BridgeError(
                "Stored line table differs from source; native file edits are blocked."
            )
        if source.count(b"\n") + 1 > MAX_PROGRAM_LINES:
            raise BridgeError("Program body exceeds the 1000-line AutoShop limit.")
        if source.count(b"\n") + 1 != self.line_count:
            raise BridgeError(
                "Line count changed. AutoShop line metadata is not understood; "
                "adding/removing lines is blocked."
            )
        if len(source) > MAX_NATIVE_SIZE:
            raise BridgeError("Source exceeds the supported size limit.")
        result = (
            self.raw[: self.length_offset]
            + struct.pack("<I", len(source))
            + encode(source)
            + self.raw[self.payload_offset + self.payload_length :]
        )
        if len(result) > MAX_NATIVE_SIZE:
            raise BridgeError("Result exceeds the supported size limit.")
        rebuilt = parse(result)
        if rebuilt.source != source or rebuilt.payload_offset != self.payload_offset:
            raise BridgeError("Rebuilt container failed structural verification.")
        return result


def parse(raw: bytes, *, allow_line_count_mismatch=False) -> Container:
    """Find exactly one UTF-8 payload followed by the observed row structure.

    Offsets and program names are discovered. The trailing structure is used as
    a discriminator, not as proof of compatibility with untested versions.
    FB envelopes independently validate the object boundary and may opt into
    observed stale row counts. Row structure/indices remain mandatory, and
    rebuild refuses edits when that count differs from the decoded source.
    """
    if len(raw) > MAX_NATIVE_SIZE or not raw.startswith(b"AutoShop"):
        raise BridgeError("Unsupported AutoShop container or size (limit 16 MiB).")
    found = []
    for offset in range(8, len(raw) - 11):
        length = struct.unpack_from("<I", raw, offset)[0]
        payload_offset = offset + 4
        end = payload_offset + length
        remaining = len(raw) - end
        if remaining < 24 or (remaining - 8) % 16:
            continue
        zero, count = struct.unpack_from("<II", raw, end)
        if zero != 0 or count != (remaining - 8) // 16:
            continue
        if any(
            struct.unpack_from("<I", raw, end + 8 + i * 16)[0] != i
            for i in range(count)
        ):
            continue
        source = decode(raw[payload_offset:end])
        try:
            validate_text(source)
        except BridgeError:
            continue
        if source.count(b"\n") + 1 != count and not allow_line_count_mismatch:
            continue
        found.append(Container(raw, offset, payload_offset, length, source, count))
        if len(found) > 1:
            raise BridgeError("Ambiguous source regions; refusing to guess.")
    if not found:
        raise BridgeError("Unsupported ST layout: no unique source/line-table match.")
    return found[0]
