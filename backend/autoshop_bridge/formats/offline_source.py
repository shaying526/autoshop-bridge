"""Isolated, experimental ST/FB candidate generation; never writes files.

Evidence: historical native insertion/deletion snapshots. Replacing the body
and rebuilding the all-zero row profile reproduces both IDE-saved ST samples.
That is historical reconstruction evidence, not an offline reload acceptance
claim. New candidates still require explicit IDE reload/save verification.

The corresponding FB snapshot pair is exactly reproduced by changing
only its body length and encoded body, retaining the entire old row table.
The FB profile follows that evidence even when body/table counts differ. It
never interprets or regenerates row metadata, or changes the stable writer.
"""

import struct

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import fb, st

ST_ZERO_ROWS_V1 = "autoshop-st-zero-row-fields-v1-experimental"
FB_PRESERVE_ROWS_V1 = "autoshop-fb-preserve-row-metadata-v1-experimental"


def rebuild_zero_row_st(raw: bytes, source: bytes, *, profile: str) -> bytes:
    """Generate one ST candidate under an explicitly selected observed profile.

    The strict standalone parser discovers boundaries; all original row fields
    except the sequential index must be zero. Unknown prefix bytes are retained.
    Nonzero rows, stale tables, malformed input and unknown profiles are refused.
    No disk, editor, backup, project registration or service operation occurs.
    """
    if profile != ST_ZERO_ROWS_V1:
        raise BridgeError("Unknown offline ST row profile.")
    st.validate_program_edit(source)
    original = st.parse(raw)
    table_offset = original.payload_offset + original.payload_length
    for index in range(original.line_table_count):
        fields = struct.unpack_from("<III", raw, table_offset + 12 + index * 16)
        if any(fields):
            raise BridgeError("Offline ST profile requires all unknown row fields zero.")
    if source == original.source:
        return raw
    count = source.count(b"\n") + 1
    rows = b"".join(struct.pack("<IIII", index, 0, 0, 0) for index in range(count))
    candidate = (
        raw[: original.length_offset]
        + struct.pack("<I", len(source))
        + st.encode(source)
        + struct.pack("<II", 0, count)
        + rows
    )
    if len(candidate) > st.MAX_NATIVE_SIZE:
        raise BridgeError("Offline ST candidate exceeds the supported size limit.")
    verified = st.parse(candidate)
    if (
        verified.source != source
        or verified.line_table_count != count
        or verified.payload_offset != original.payload_offset
        or candidate[: verified.length_offset] != raw[: original.length_offset]
    ):
        raise BridgeError("Offline ST candidate failed structural verification.")
    return candidate


def rebuild_preserved_row_fb(raw: bytes, source: bytes, *, profile: str) -> bytes:
    """Generate an FB candidate, retaining existing row metadata verbatim.

    The existing FB parser validates a unique embedded ST object and complete
    variable table, including empty variable tables. Its observed stale-count
    support is retained: body line count is not the stored record count. This
    profile does not assert metadata freshness, reinterpret row indices as body
    positions, or manufacture metadata for newly inserted lines. Outer bytes,
    variable records, inner prefix, and the complete trailing row table remain
    identical. The result still needs actual closed-project reload acceptance.
    """
    if profile != FB_PRESERVE_ROWS_V1:
        raise BridgeError("Unknown offline FB row profile.")
    st.validate_program_edit(source)
    original = fb.parse(raw)
    if source == original.source:
        return raw
    old_end = original.payload_offset + original.payload_length
    candidate = (
        raw[: original.length_offset]
        + struct.pack("<I", len(source))
        + st.encode(source)
        + raw[old_end:]
    )
    if len(candidate) > st.MAX_NATIVE_SIZE:
        raise BridgeError("Offline FB candidate exceeds the supported size limit.")
    verified = fb.parse(candidate)
    new_end = verified.payload_offset + verified.payload_length
    if (
        verified.source != source
        or verified.inner_offset != original.inner_offset
        or verified.payload_offset != original.payload_offset
        or verified.line_table_count != original.line_table_count
        or verified.variable_document() != original.variable_document()
        or candidate[: verified.length_offset] != raw[: original.length_offset]
        or candidate[new_end:] != raw[old_end:]
    ):
        raise BridgeError("Offline FB candidate failed envelope/metadata verification.")
    return candidate
