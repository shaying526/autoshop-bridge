"""Pure declaration-deletion candidates, without project authority.

Only complete records already decoded by the existing FB/FC/STRU/GVT/FBI readers
are removed. References are not checked and no changes cascade. IDE acceptance,
allocation, registration and recovery are outside this candidate builder.
Empty results require an observed FB/FC/GVT layout. The observed IDE disables
deletion of the last structure member. FBI candidates retain at least one
instance and preserve both opaque surrounding containers byte for byte.
"""

import struct

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import empty_table, fb, fc, instances, tables
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.storage import sha256

PROFILE = "declaration-delete-candidate-v3"


def _layout(raw, kind):
    if not isinstance(raw, bytes) or len(raw) > MAX_NATIVE_SIZE:
        raise BridgeError("Expected bounded native declaration bytes.")
    if not isinstance(kind, str) or kind not in ("fb", "fc", "stru", "gvt", "fbi"):
        raise BridgeError("Deletion supports only FB/FC/STRU/GVT/FBI candidates.")
    if kind == "fbi":
        document = instances.parse(raw)
        if (document["profile"] != instances.PROFILE
                or document["coverage"] != "instance_segment_only"
                or document["instance_count"] < 1):
            raise BridgeError("Deletion requires the observed nonempty FBI instance-record segment.")
        count_offset = document["record_segment_offset"]
        count = struct.unpack_from("<I", raw, count_offset)[0]
        rows = tuple((v["name"], v["record_offset"], v["record_offset"] + v["record_bytes"])
                     for v in document["instances"])
        end = count_offset + document["record_segment_bytes"]
        if not raw[end:].startswith(instances.MAGIC):
            raise BridgeError("FBI instance records lack the observed following container boundary.")
    elif kind in ("fb", "fc"):
        container = (fb if kind == "fb" else fc).parse(raw)
        reader = fb.Reader(raw, container.variable_header_offset, container.inner_offset - 4)
        reader.string()
        if reader.u32() != (256 if kind == "fb" else 512):
            raise BridgeError("Unexpected declaration header.")
        count_offset = reader.pos
        count = reader.u32()
        rows = tuple((v.name, v.offset, v.end) for v in container.variables)
        end = container.inner_offset - 4
    else:
        container = tables.parse(raw, kind)
        count_offset = container.count_offset
        count = struct.unpack_from("<I", raw, count_offset)[0]
        rows = tuple((v.name, v.start, v.end) for v in container.rows)
        end = len(raw)
    if count != len(rows):
        raise BridgeError("Declaration count differs from parsed records.")
    cursor, names = count_offset + 4, set()
    for name, start, stop in rows:
        if start != cursor or stop <= start or stop > end or name.casefold() in names:
            raise BridgeError("Declaration boundaries or case-insensitive names are ambiguous.")
        cursor = stop
        names.add(name.casefold())
    if cursor != end:
        raise BridgeError("Declaration records do not cover the exact record region.")
    return count_offset, end, rows


def record_baselines(raw, kind):
    """Return exact-name/whole-record SHA-256 pairs from the supplied bytes.

    These hashes identify declarations, including opaque fields. They do not
    replace a complete target/project baseline or authorize a deletion.
    """
    _, _, rows = _layout(raw, kind)
    return [dict(name=name, record_sha256=sha256(raw[start:end]))
            for name, start, end in rows]


def rebuild(raw, kind, operations):
    """Delete exact hash-matched records, allowing observed FB/FC/GVT empty layouts.

    All operations refer to this input's original records. Only the four-byte
    count and requested complete record spans may change. Prefix, surviving
    record bytes and suffix (including embedded ST metadata) remain exact.
    No implicit rename, address compaction, initializer rewrite or cascade occurs.
    """
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit declaration delete operations.")
    count_offset, end, rows = _layout(raw, kind)
    by_name = {name: (start, stop) for name, start, stop in rows}
    deleted, seen = set(), set()
    for op in operations:
        if (not isinstance(op, dict)
                or set(op) != {"op", "name", "expected_record_sha256"}
                or op.get("op") != "delete"
                or not isinstance(op.get("name"), str)):
            raise BridgeError("Delete requires exact op/name/expected_record_sha256 fields.")
        name, expected = op["name"], op["expected_record_sha256"]
        if name.casefold() in seen:
            raise BridgeError("Duplicate declaration deletion target.")
        seen.add(name.casefold())
        if name not in by_name:
            raise BridgeError("Expected one exact existing declaration name.")
        if (not isinstance(expected, str) or len(expected) != 64
                or any(c not in "0123456789abcdef" for c in expected)):
            raise BridgeError("Expected a lowercase declaration record SHA-256.")
        start, stop = by_name[name]
        if sha256(raw[start:stop]) != expected:
            raise BridgeError("Declaration record baseline differs: {}.".format(name))
        deleted.add(name)
    remaining = [(name, start, stop) for name, start, stop in rows if name not in deleted]
    if not remaining and kind == "stru":
        raise BridgeError("Deleting the last declaration in a structure is unsupported by the observed IDE; retain at least one member.")
    if not remaining and kind == "fbi":
        raise BridgeError("Deleting the last FBI instance requires separate IDE empty-table transition evidence.")
    records = [raw[start:stop] for _, start, stop in remaining]
    result = (raw[:count_offset] + struct.pack("<I", len(remaining))
              + b"".join(records) + raw[end:])
    if not remaining and kind == "gvt" and empty_table.count_offset(result) != count_offset:
        raise BridgeError("Deleting the last declaration requires the observed empty GVT profile.")
    new_count, new_end, new_rows = _layout(result, kind)
    if (new_count != count_offset or result[:new_count] != raw[:count_offset]
            or result[new_end:] != raw[end:]
            or [name for name, _, _ in new_rows] != [name for name, _, _ in remaining]
            or [result[start:stop] for _, start, stop in new_rows] != records):
        raise BridgeError("Deletion candidate failed exact envelope/record preservation.")
    return result
