"""Pure FB variable candidates; no registration, files, IDE or address allocation.

The caller must prove registered FB/type identity, freeze definition hashes and
provide backup/conflict protection before any write. These candidates still need
IDE reopen/save/compile acceptance. No GVT complex encoder is inferred here.
"""

import struct

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import fb, tables
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.projects.identifiers import precheck_addition_names

PROFILE = "fb-flat-scalar-variables-candidate-v1"
SCALARS = {"BOOL": 1, "INT": 4, "DINT": 16}


def _text(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise BridgeError("Expected bounded text without control characters.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise BridgeError("Invalid Unicode in FB declaration.") from exc
    if size > 4096:
        raise BridgeError("FB declaration text exceeds size limit.")


def _initial(code, value):
    _text(value)
    row = tables.Row(0, 0, "", code, "", "", None, {}, {})
    tables.validate_value(row, "initial_value", value)


def flat_structure_initial(raw, name):
    """Observed flat scalar profiles; reject unobserved default grammars.

    Nonempty scalar-member comments were observed in saved IN/OUT structures.
    All-empty comments produce an empty initializer. Mixed comments, nested
    types, strings and explicit defaults require their own evidence profile.
    AutoShop V4.11.0.5 saves literal '=' and '#' inside member comments
    unchanged (INOUT probe, 2026-10-26). No escaping is inferred for other
    initializer delimiters; definition comments themselves are never rewritten.
    """
    definition = tables.parse(raw, "stru")
    if definition.name != name or not definition.rows:
        raise BridgeError("Expected the exact nonempty structure definition.")
    parts = []
    for index, row in enumerate(definition.rows):
        if row.type_code not in SCALARS.values() or row.type_text not in (
            "", tables.TYPES.get(row.type_code)
        ):
            raise BridgeError("Only observed flat BOOL/INT/DINT structures are candidates.")
        _text(row.comment)
        positions = [i for i, c in enumerate(row.comment) if c in "(),:"]
        if positions:
            raise FormatRejection(
                "Structure initializer comment grammar needs an IDE probe: "
                "structure={!r}, member={} {!r}, comment={!r}, unobserved characters={!r}.".format(
                    name, index + 1, row.name, row.comment,
                    [row.comment[i] for i in positions]),
                code="offline_initializer_comment_unobserved",
                context=dict(stage="fb_structure_initializer", structure=name,
                             member=row.name, member_index=index, field="comment",
                             comment=row.comment, characters=[row.comment[i] for i in positions],
                             character_positions=positions, index_base=0,
                             reason="unobserved_delimiter", requires="independent_ide_probe"),
            )
        if row.comment:
            parts.append(row.name + ":=\x07" + row.comment)
    if not parts:
        return ""
    if len(parts) != len(definition.rows):
        raise BridgeError("Mixed structure comments require a separate initializer profile.")
    return "(" + ", ".join(parts) + ")"


def _record(op, definitions):
    dtype, category = op["data_type"], op["category"]
    _text(dtype)
    if not isinstance(dtype, str) or not isinstance(category, str) or category not in fb.CATEGORIES.values():
        raise BridgeError("Unsupported FB type/category.")
    code, type_text = SCALARS.get(dtype), ""
    initial = op["initial_value"]
    if code is None:
        if category not in ("VAR", "IN", "OUT", "INOUT") or dtype not in definitions or initial is not None:
            raise BridgeError("Named-type additions require an explicit definition and null initializer.")
        try:
            block = fb.parse(definitions[dtype])
        except BridgeError:
            block = None
        type_text = dtype
        if block is not None:
            if block.program_name != dtype or category != "VAR":
                raise FormatRejection(
                    "Project FB instances require the exact type identity and category VAR.",
                    code="offline_unsupported_fb_instance",
                    context=dict(variable=op["name"], data_type=dtype, category=category,
                                 definition_name=block.program_name, field="category" if category != "VAR" else "data_type"),
                )
            # Normal V4.11.0.5 saves of project FBs with scalar and structure
            # interfaces produce this empty default. No transitive initializer
            # or layout/address is synthesized from the referenced definition.
            code, type_text, initial = 256, dtype.upper(), ""
        else:
            code = 64
            try:
                initial = flat_structure_initial(definitions[dtype], dtype)
            except FormatRejection as exc:
                exc.context.update(variable=op["name"], category=category)
                raise
    elif category == "INOUT":
        if initial is not None:
            raise BridgeError("INOUT requires a null independent initializer.")
        initial = "OFF" if code == 1 else "0"
    else:
        _initial(code, initial)
    _text(op["comment"])
    return (tables.string(type_text) + struct.pack("<I", code)
            + tables.string(op["name"]) + tables.string(op["comment"])
            + tables.string(initial) + struct.pack("<IIII", next(
                k for k, v in fb.CATEGORIES.items() if v == category), 1, 0xFFFFFFFF, 0))


def rebuild_fb(raw, operations, structure_definitions=None):
    """Return bytes with exact existing-record/prefix/embedded-object preservation.

    ``structure_definitions`` retains its historical argument name and maps
    exact type names to caller-validated native STRU or LiteST FB bytes.
    Registration and stale-hash checks belong to the caller. Neither
    addresses nor opaque tail fields can be supplied through this API.
    """
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit FB variable operations.")
    try:
        precheck_addition_names(dict(schema=1, operations=operations))
    except UnicodeError as exc:
        raise BridgeError("Invalid Unicode in FB declaration.") from exc
    definitions = {} if structure_definitions is None else structure_definitions
    if not isinstance(definitions, dict):
        raise BridgeError("Type definitions must be an exact name/bytes mapping.")
    result = raw
    for operation_index, op in enumerate(operations):
        before = fb.parse(result)
        header = fb.Reader(result, before.variable_header_offset, before.inner_offset - 4)
        header.string()
        if header.u32() != 256:
            raise BridgeError("Unsupported FB variable header.")
        count_offset = header.pos
        header.u32()
        if not isinstance(op, dict):
            raise BridgeError("Variable operation must be an object.")
        if op.get("op") == "add":
            if set(op) != {"op", "name", "data_type", "category", "initial_value", "comment"}:
                raise BridgeError("Add requires the exact FB declaration fields.")
            _text(op["name"])
            if (not tables.identifier(op["name"]) or len(before.variables) >= 4096
                    or any(v.name.casefold() == op["name"].casefold() for v in before.variables)):
                raise BridgeError("Invalid/duplicate FB variable or variable limit exceeded.")
            try:
                encoded = _record(op, definitions)
            except FormatRejection as exc:
                exc.context["operation_index"] = operation_index
                raise
            pos = before.inner_offset - 4
            result = (result[:count_offset] + struct.pack("<I", len(before.variables) + 1)
                      + result[count_offset + 4:pos] + encoded + result[pos:])
        elif op.get("op") == "set":
            if set(op) != {"op", "name", "field", "expected", "value"}:
                raise BridgeError("Set requires exact name/field/expected/value.")
            rows = [v for v in before.variables if v.name == op["name"]]
            if len(rows) != 1 or op["field"] not in ("comment", "initial_value"):
                raise BridgeError("Expected one existing variable and supported field.")
            row = rows[0]
            reader = fb.Reader(result, row.offset, row.end)
            reader.string()
            reader.u32()
            reader.string()
            spans = {}
            for key in ("comment", "initial_value"):
                start = reader.pos
                value = reader.string()
                spans[key] = (start, reader.pos, value)
            start, end, old_value = spans[op["field"]]
            if not isinstance(op["expected"], str) or op["expected"] != old_value:
                raise BridgeError("FB variable field baseline differs.")
            _text(op["value"])
            if op["field"] == "initial_value":
                if row.fields[0] == 3:
                    raise BridgeError("INOUT has no independent initializer.")
                _initial(row.type_code, op["value"])
            if old_value != op["value"]:
                result = result[:start] + tables.string(op["value"]) + result[end:]
        else:
            raise BridgeError("Unsupported FB operation.")
        if len(result) > MAX_NATIVE_SIZE:
            raise BridgeError("FB candidate exceeds size limit.")
        after = fb.parse(result)
        if (result[:before.variable_header_offset] != before.raw[:before.variable_header_offset]
                or result[after.inner_offset - 4:] != before.raw[before.inner_offset - 4:]):
            raise BridgeError("FB candidate changed opaque envelope or embedded ST bytes.")
    return result
