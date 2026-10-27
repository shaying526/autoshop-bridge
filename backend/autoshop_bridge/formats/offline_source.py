"""Isolated, experimental ST/FB candidate generation; never writes files.

Evidence: historical native insertion/deletion snapshots. Replacing the body
and rebuilding the all-zero row profile reproduces both IDE-saved ST samples.
V4.11.0.5 ST fold rows additionally have observed depth/header/expanded fields;
the separate fold-cache profile relocates these annotations with logical lines.
New host/layout candidates still require explicit IDE reload/save verification.

The corresponding FB snapshot pair is exactly reproduced by changing
only its body length and encoded body, retaining the entire old row table.
The FB profile follows that evidence even when body/table counts differ. It
never interprets or regenerates row metadata, or changes the stable writer.
"""

import struct
from difflib import SequenceMatcher

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import fb, st

ST_ZERO_ROWS_V1 = "autoshop-st-zero-row-fields-v1-experimental"
FB_PRESERVE_ROWS_V1 = "autoshop-fb-preserve-row-metadata-v1-experimental"
ST_FOLD_ROWS_V1 = "autoshop-st-relocated-fold-row-cache-v1-experimental"


def _row_rejection(index, field, value, offset, reason, profile):
    raise FormatRejection(
        "Unsupported ST row metadata at line {}: {}={} ({}).".format(index + 1, field, value, reason),
        code="offline_unsupported_st_row_metadata",
        context=dict(profile=profile, line=index + 1, row_index=index, field=field,
                     value=value, byte_offset=offset, reason=reason),
    )


def rebuild_fold_row_st(raw: bytes, source: bytes, *, profile: str) -> bytes:
    """Relocate the observed ST lexical fold cache with exact matching lines.

    V4.11.0.5 normal saves and scalar Scintilla observations identify depth,
    header and expanded fields. They are editor cache, not executable data.
    Equal lines retain the three original fields, deleted lines lose their
    records, and inserted/replaced lines start with the observed neutral record.
    AutoShop re-lexes depth/header on load and normal save. This does not parse
    or validate business syntax, invent fold states, or change the stable writer.
    """
    if profile != ST_FOLD_ROWS_V1:
        raise BridgeError("Unknown offline ST fold-row profile.")
    st.validate_program_edit(source)
    original = st.parse(raw)
    if original.line_count > st.MAX_PROGRAM_LINES:
        raise BridgeError("Offline ST fold-cache relocation exceeds the 1000-line input limit.")
    offset = original.payload_offset + original.payload_length + 8
    old_rows = []
    for index in range(original.line_table_count):
        depth, header, expanded = struct.unpack_from("<III", raw, offset + index * 16 + 4)
        # Scintilla's 12-bit level includes the 0x400 base. No high flags belong
        # in the native relative-depth field; header/expanded are separate BOOLs.
        for field, value, delta, valid in (
            ("fold_depth", depth, 4, depth <= 0xBFF),
            ("fold_header", header, 8, header in (0, 1)),
            ("fold_expanded", expanded, 12, expanded in (0, 1) and (header == 1 or expanded == 0)),
        ):
            if not valid:
                _row_rejection(index, field, value, offset + index * 16 + delta,
                               "outside observed fold-cache layout", profile)
        old_rows.append((depth, header, expanded))
    if source == original.source:
        return raw
    # Keep LF+1 indexing, including a final empty logical row. CRLF and LF have
    # the same logical content for matching, without changing source bytes.
    old_lines = [line.removesuffix(b"\r") for line in original.source.split(b"\n")]
    new_lines = [line.removesuffix(b"\r") for line in source.split(b"\n")]
    new_rows = [(0, 0, 0)] * len(new_lines)
    for block in SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_matching_blocks():
        new_rows[block.b:block.b + block.size] = old_rows[block.a:block.a + block.size]
    result = (raw[:original.length_offset] + struct.pack("<I", len(source)) + st.encode(source)
              + struct.pack("<II", 0, len(new_lines))
              + b"".join(struct.pack("<IIII", i, *row) for i, row in enumerate(new_rows)))
    if len(result) > st.MAX_NATIVE_SIZE:
        raise BridgeError("Offline ST candidate exceeds the supported size limit.")
    verified = st.parse(result)
    if (verified.source != source or verified.line_table_count != len(new_lines)
            or verified.payload_offset != original.payload_offset
            or result[:verified.length_offset] != raw[:original.length_offset]):
        raise BridgeError("Offline ST fold-row candidate failed structural verification.")
    return result


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
