"""Independent FC scalar-add profile; no initializer or FB retention fields.

Existing records and the entire embedded ST object are opaque preserved bytes.
The workflow owns registration, closed-project checks, backups and readback.
"""

import struct

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import fc, tables
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.projects.identifiers import precheck_addition_names

PROFILE = "fc-scalar-add-unallocated-v1"
SCALARS = {"BOOL": 1, "INT": 4, "DINT": 16}
CATEGORIES = {"VAR": 0, "IN": 1, "OUT": 2, "INOUT": 3}


def _text(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise BridgeError("FC declaration requires text without control characters.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise BridgeError("Invalid Unicode in FC declaration.") from exc
    if size > 4096:
        raise BridgeError("FC declaration text exceeds size limit.")


def rebuild(raw, operations):
    """Append 1..32 explicit scalar declarations to an identified ST FC.

    New records use the observed category/FFFFFFFF/0 tail. These are not
    borrowed addresses or an interpretation of arbitrary existing tail fields.
    Empty, compact and stale-line-table bodies are preserved without rebuilding.
    """
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit FC additions.")
    before = fc.parse(raw)
    names = {v.name.casefold() for v in before.variables}
    encoded = []
    for op in operations:
        if (not isinstance(op, dict)
                or set(op) != {"op", "name", "data_type", "category", "initial_value", "comment"}
                or op["op"] != "add"):
            raise BridgeError("Offline FC supports exact scalar add fields only.")
        for key in ("name", "data_type", "category", "comment"):
            _text(op[key])
        if (not tables.identifier(op["name"]) or op["name"].casefold() in names
                or op["data_type"] not in SCALARS or op["category"] not in CATEGORIES
                or op["initial_value"] is not None):
            raise BridgeError("FC additions require unique BOOL/INT/DINT declarations and initial_value=null.")
        precheck_addition_names(dict(schema=1, operations=[op]))
        names.add(op["name"].casefold())
        encoded.append(tables.string("") + struct.pack("<I", SCALARS[op["data_type"]])
                       + tables.string(op["name"]) + tables.string(op["comment"])
                       + struct.pack("<III", CATEGORIES[op["category"]], 0xFFFFFFFF, 0))
    if len(names) > 4096:
        raise BridgeError("FC variable limit exceeded.")
    header = fc.Reader(raw, before.variable_header_offset, before.inner_offset - 4)
    header.string()
    if header.u32() != 512:
        raise BridgeError("Unsupported FC variable header.")
    count_offset = header.pos
    if header.u32() != len(before.variables):
        raise BridgeError("FC variable count differs from parsed records.")
    end = before.inner_offset - 4
    result = (raw[:count_offset] + struct.pack("<I", len(names))
              + raw[count_offset + 4:end] + b"".join(encoded) + raw[end:])
    if len(result) > MAX_NATIVE_SIZE:
        raise BridgeError("FC candidate exceeds size limit.")
    after = fc.parse(result)
    if (len(after.variables) != len(names)
            or result[:count_offset] != raw[:count_offset]
            or result[after.inner_offset - 4:] != raw[end:]
            or any(raw[a.offset:a.end] != result[b.offset:b.end]
                   for a, b in zip(before.variables, after.variables))
            or [result[v.offset:v.end] for v in after.variables[len(before.variables):]] != encoded):
        raise BridgeError("FC candidate failed complete record/envelope/body preservation.")
    return result
