"""Pure FB variable candidates; no registration, files, IDE or address allocation.

The caller identifies registered types or explicitly selects a library FB
record kind, freezes project hashes and protects writes. Candidates still need
IDE reopen/save/compile acceptance. No GVT complex encoder is inferred here.
"""

import struct
from dataclasses import dataclass

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import fb, tables
from autoshop_bridge.formats.scalar_types import descriptor
from autoshop_bridge.formats.structure import comment_initializer, flat_scalar_definition
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.projects.identifiers import precheck_addition_names

PROFILE = "fb-flat-scalar-variables-candidate-v1"


@dataclass(frozen=True)
class FBInstanceType:
    """Explicit FB record identity, not a parsed graph or semantic proof.

    The workflow freezes direct-HCP LD identities or records the caller's
    explicit library FB choice. No native definition/layout is fabricated.
    """
    name: str
    source: str


def instance_definition(name, definition):
    if isinstance(definition, FBInstanceType):
        if definition.name != name or definition.source not in ("registered_ld", "explicit_request"):
            raise BridgeError("FB record type descriptor identity differs.")
        return definition
    parsed = fb.parse(definition)
    if parsed.program_name != name:
        raise BridgeError("Project FB definition identity differs.")
    return FBInstanceType(name, "registered_litest")


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
    if code == 2048:
        # The observed STRING record uses the same native text field. Preserve
        # its spelling; capacity/literal semantics are checked by AutoShop.
        return
    row = tables.Row(0, 0, "", code, "", "", None, {}, {})
    tables.validate_value(row, "initial_value", value)


def flat_structure_initial(raw, name):
    """Observed flat scalar profiles; reject unobserved default grammars.

    Nonempty scalar-member comments were observed in saved IN/OUT structures.
    All-empty comments produce an empty initializer. Mixed comments use the
    same position-based separator rule observed in VAR/IN/OUT/INOUT saves on
    2026-10-28. REAL and canonical STRING members were independently saved
    across all categories on 2026-10-30; additional VAR saves confirm native
    comment separators 6/8 and CRLF. Nested types and explicit defaults remain
    unsupported.
    AutoShop V4.11.0.5 saves literal '=' and '#' inside member comments
    unchanged (INOUT probe, 2026-10-26). No escaping is inferred for other
    initializer delimiters; definition comments themselves are never rewritten.
    """
    definition = flat_scalar_definition(raw, name)
    for index, row in enumerate(definition.rows):
        # These are saved native separators, not user input. Keep their bytes
        # in the generated template; do not apply display normalization here.
        crlf = {position for i in range(len(row.comment) - 1)
                if row.comment[i:i + 2] == "\r\n" for position in (i, i + 1)}
        controls = {i for i, c in enumerate(row.comment)
                    if ord(c) < 32 and c not in "\x06\x08" and i not in crlf}
        positions = [i for i, c in enumerate(row.comment) if c in "(),:" or i in controls]
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
                             reason="unobserved_control" if controls else "unobserved_delimiter",
                             requires="independent_ide_probe"),
            )
        _text(row.comment.replace("\x06", "").replace("\x08", "").replace("\r\n", ""))
        if len(row.comment.encode("utf-8")) > 4096:
            raise BridgeError("Structure member comment exceeds the supported native text limit.")
    return comment_initializer((row.name, row.comment) for row in definition.rows)


def _record(op, definitions):
    dtype, category = op["data_type"], op["category"]
    _text(dtype)
    if not isinstance(dtype, str) or not isinstance(category, str) or category not in fb.CATEGORIES.values():
        raise BridgeError("Unsupported FB type/category.")
    scalar = descriptor(dtype)
    code, type_text = (scalar.code, scalar.type_text) if scalar else (None, "")
    initial = op["initial_value"]
    if code is None:
        if category not in ("VAR", "IN", "OUT", "INOUT") or dtype not in definitions or initial is not None:
            raise BridgeError("Named-type additions require an explicit definition and null initializer.")
        definition = definitions[dtype]
        try:
            block = instance_definition(dtype, definition)
        except BridgeError:
            if isinstance(definition, FBInstanceType):
                raise
            block = None
        type_text = dtype
        if block is not None:
            if category != "VAR":
                raise FormatRejection(
                    "Project FB instances require the exact type identity and category VAR.",
                    code="offline_unsupported_fb_instance",
                    context=dict(variable=op["name"], data_type=dtype, category=category,
                                 definition_name=block.name, field="category"),
                )
            if block.source == "explicit_request" and op.get("type_kind") != "function_block":
                raise BridgeError("Library VAR additions require type_kind=function_block to distinguish FBs from structures.")
            # Normal V4.11.0.5 saves of project FBs with scalar and structure
            # interfaces produce this empty default. No transitive initializer
            # or layout/address is synthesized from the referenced definition.
            code, type_text, initial = 256, dtype.upper(), ""
        else:
            if "type_kind" in op:
                raise BridgeError("Explicit function_block kind conflicts with a structure definition.")
            code = 64
            try:
                initial = flat_structure_initial(definitions[dtype], dtype)
            except FormatRejection as exc:
                exc.context.update(variable=op["name"], category=category)
                raise
    elif "type_kind" in op:
        raise BridgeError("Explicit function_block kind conflicts with a scalar type.")
    elif category == "INOUT":
        if initial is not None:
            raise BridgeError("INOUT requires a null independent initializer.")
        initial = {1: "OFF", 4: "0", 16: "0", 32: "0.000000", 2048: ""}[code]
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
    exact type names to native STRU/LiteST bytes or explicit FBInstanceType.
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
        raise BridgeError("Type definitions must map exact names to native bytes or FB descriptors.")
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
            fields = {"op", "name", "data_type", "category", "initial_value", "comment"}
            if set(op) not in (fields, fields | {"type_kind"}) or ("type_kind" in op and op["type_kind"] != "function_block"):
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
