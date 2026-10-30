"""Pure, evidence-bounded GVT candidates; addresses are allocated by the IDE.

The caller verifies registered type identity, dependency hashes, cross-table
names and backup/conflict protection. No file or desktop access occurs here.
"""

import struct

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import tables
from autoshop_bridge.formats.scalar_types import descriptor
from autoshop_bridge.formats.structure import flat_scalar_definition
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.projects.identifiers import precheck_addition_names

PROFILE = "gvt-flat-structure-unallocated-v1"


def _validate_structure(raw, name):
    flat_scalar_definition(raw, name)


def _text(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise BridgeError("Expected bounded text without control characters.")
    try:
        length = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise BridgeError("Invalid Unicode in GVT declaration.") from exc
    if length > 4096:
        raise BridgeError("GVT declaration text exceeds size limit.")


def rebuild(raw, operations, structure_definitions=None):
    """Build exact GVT set/scalar-add/flat-structure-add candidates.

    Structure additions require initial_value=null, producing the observed empty
    native initializer. They use flags 257, address FFFFFFFF, no device mapping,
    zero trailing fields and exact type name. Allocation is never copied.
    """
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit GVT operations.")
    try:
        precheck_addition_names(dict(schema=1, operations=operations))
    except UnicodeError as exc:
        raise BridgeError("Invalid Unicode in GVT declaration.") from exc
    definitions = {} if structure_definitions is None else structure_definitions
    if not isinstance(definitions, dict):
        raise BridgeError("Expected exact structure name/bytes mapping.")
    result = raw
    for op in operations:
        table = tables.parse(result, "gvt")
        if not isinstance(op, dict):
            raise BridgeError("GVT operation must be an object.")
        if op.get("op") == "add":
            if set(op) != {"op", "name", "data_type", "comment", "initial_value"}:
                raise BridgeError("GVT add requires exact declaration fields.")
            for key in ("name", "data_type", "comment"):
                _text(op[key])
            if not tables.identifier(op["name"]) or any(
                    row.name.casefold() == op["name"].casefold() for row in table.rows):
                raise BridgeError("Invalid/duplicate GVT variable name.")
            if descriptor(op["data_type"]) is None:
                name = op["data_type"]
                if name not in definitions or op["initial_value"] is not None:
                    raise BridgeError("Structure add requires a known definition and null initializer.")
                _validate_structure(definitions[name], name)
                if len(table.rows) >= 4096:
                    raise BridgeError("GVT row limit exceeded.")
                record = (struct.pack("<II", 64, 64) + tables.string(op["name"])
                          + tables.string("") + struct.pack("<II", 257, 0xFFFFFFFF)
                          + tables.string(op["comment"]) + b"\xff\xfe\xff\0"
                          + struct.pack("<II", 0, 0) + tables.string(name))
                pos = table.count_offset
                result = (result[:pos] + struct.pack("<I", len(table.rows) + 1)
                          + result[pos + 4:] + record)
            else:
                _text(op["initial_value"])
                result = table.rebuild([op])
        elif op.get("op") == "set":
            if set(op) != {"op", "name", "field", "expected", "value"}:
                raise BridgeError("GVT set requires exact field/baseline/value.")
            _text(op["value"])
            result = table.rebuild([op])
        else:
            raise BridgeError("Unsupported GVT operation.")
        if len(result) > MAX_NATIVE_SIZE:
            raise BridgeError("GVT result exceeds size limit.")
        after = tables.parse(result, "gvt")
        if result[:table.count_offset] != table.raw[:table.count_offset]:
            raise BridgeError("GVT opaque envelope changed.")
        if op["op"] == "add":
            if len(after.rows) != len(table.rows) + 1 or any(
                    table.raw[a.start:a.end] != result[b.start:b.end]
                    for a, b in zip(table.rows, after.rows)):
                raise BridgeError("GVT addition changed existing records.")
    return result
