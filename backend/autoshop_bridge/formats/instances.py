"""Read-only, uniquely bounded instance-record segment in observed FBI files.

The surrounding CArchive containers are opaque. No serializer, writable fields,
or full-container validation is provided by this module.
"""

import struct

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.fb import Reader
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.storage import sha256
from autoshop_bridge.formats.tables import unicode_string
from autoshop_bridge.formats.empty_table import instance_segment as empty_segment

PROFILE = "autoshop-fbi-instance-segment-v1-read-only"
MAGIC = b"AutoShop"
EMPTY_PROFILE = "autoshop-fbi-empty-tables-v1-read-only"


def _document(raw, start, end, rows, profile=PROFILE):
    return dict(
        schema=1, read_only=True, profile=profile, coverage="instance_segment_only",
        instance_count=len(rows), instances=rows, record_segment_offset=start,
        record_segment_bytes=end-start, opaque_prefix_bytes=start,
        opaque_prefix_sha256=sha256(raw[:start]), opaque_suffix_bytes=len(raw)-end,
        opaque_suffix_sha256=sha256(raw[end:]), limitations=[
            "Only the uniquely bounded instance-record segment is parsed.",
            "Surrounding archive metadata and nested initializer syntax remain opaque.",
            "No native instance-table serializer, registration or allocation is implemented.",
        ],
    )


def qualified_name(value):
    return (
        bool(value)
        and len(value.encode("utf-8")) <= 512
        and all(part.isidentifier() for part in value.split("."))
    )


def parse(raw):
    if (
        not isinstance(raw, bytes)
        or not raw.startswith(MAGIC)
        or len(raw) > MAX_NATIVE_SIZE
    ):
        raise BridgeError("Unsupported FBI header/size.")
    candidates = []
    empty = empty_segment(raw)
    if empty is not None:
        candidates.append(_document(raw, empty[0], empty[1], [], EMPTY_PROFILE))
    # Discover the count/record sequence near the front, not a project offset.
    for start in range(8, min(len(raw) - 11, 4096)):
        count = struct.unpack_from("<I", raw, start)[0]
        if not 1 <= count <= 4096 or raw[start + 4 : start + 12] != struct.pack(
            "<II", 256, 256
        ):
            continue
        reader = Reader(raw, start + 4, len(raw))
        rows, names = [], set()
        try:
            for order in range(count):
                record_start = reader.pos
                if reader.u32() != 256 or reader.u32() != 256:
                    raise BridgeError("Unsupported instance type descriptor.")
                name, initial = reader.string(), reader.string()
                flags, address = reader.u32(), reader.u32()
                comment, device = reader.string(), unicode_string(reader)
                fields = [reader.u32(), reader.u32()]
                type_name, tail = reader.string(), reader.take(8)
                if (
                    not name.isidentifier()
                    or name.casefold() in names
                    or not qualified_name(type_name)
                    or tail != b"\xff" * 8
                ):
                    raise BridgeError("Unsupported/duplicate instance definition.")
                names.add(name.casefold())
                rows.append(
                    dict(
                        name=name,
                        data_type=type_name,
                        type_text_raw=type_name,
                        type_code=256,
                        comment=comment,
                        initial_value_raw=initial,
                        display_order=order + 1,
                        record_offset=record_start,
                        record_bytes=reader.pos - record_start,
                        uninterpreted_metadata=dict(
                            flags_raw=flags,
                            address_raw=address,
                            device_address_text=device,
                            trailing_fields_raw=fields,
                        ),
                    )
                )
            # A second native container follows all observed instance records.
            # It is not decoded or used to infer more declarations.
            if not raw[reader.pos :].startswith(MAGIC):
                continue
            candidates.append(_document(raw, start, reader.pos, rows))
        except BridgeError:
            continue
    if len(candidates) != 1:
        raise BridgeError("Unsupported/ambiguous FBI instance-record segment.")
    return candidates[0]
