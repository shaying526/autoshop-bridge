"""Pure FB variable candidates; no registration, files, IDE or address allocation.

The caller identifies registered types or explicitly selects a library FB
record kind, freezes project hashes and protects writes. Candidates still need
IDE reopen/save/compile acceptance. No GVT complex encoder is inferred here.
"""

import struct
from dataclasses import dataclass

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import fb, tables
from autoshop_bridge.formats.array_types import descriptor as array_descriptor
from autoshop_bridge.formats.scalar_types import descriptor, ARRAY_ELEMENT_CODES
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


def _validate_member_comment(row, index, name, stage="fb_structure_initializer"):
    # These are saved native separators, not user input. Keep their bytes
    # in generated templates; never apply display normalization here.
    native_separators = "\x03\x04\x05\x06\x08"
    crlf = {position for i in range(len(row.comment) - 1)
            if row.comment[i:i + 2] == "\r\n" for position in (i, i + 1)}
    controls = {i for i, c in enumerate(row.comment)
                if ord(c) < 32 and c not in native_separators and i not in crlf}
    positions = [i for i, c in enumerate(row.comment) if c in "(),:" or i in controls]
    if positions:
        raise FormatRejection(
            "Structure initializer comment grammar needs an IDE probe: "
            "structure={!r}, member={} {!r}, comment={!r}, unobserved characters={!r}.".format(
                name, index + 1, row.name, row.comment,
                [row.comment[i] for i in positions]),
            code="offline_initializer_comment_unobserved",
            context=dict(stage=stage, structure=name,
                         member=row.name, member_index=index, field="comment",
                         comment=row.comment, characters=[row.comment[i] for i in positions],
                         character_positions=positions, index_base=0,
                         reason="unobserved_control" if controls else "unobserved_delimiter",
                         requires="independent_ide_probe"),
        )
    _text("".join(c for c in row.comment if c not in native_separators).replace("\r\n", ""))
    if len(row.comment.encode("utf-8")) > 4096:
        raise BridgeError("Structure member comment exceeds the supported native text limit.")


def flat_structure_initial(raw, name, *, allow_complex=False):
    """Observed flat scalar profiles; reject unobserved default grammars.

    Nonempty scalar-member comments were observed in saved IN/OUT structures.
    All-empty comments produce an empty initializer. Mixed comments use the
    same position-based separator rule observed in VAR/IN/OUT/INOUT saves on
    2026-10-28. REAL and canonical STRING members were independently saved
    across all categories on 2026-10-30; BYTE/IP members across all categories
    on 2026-10-31. Normal ordinary/ARRAY saves on that date also confirm saved
    member-comment separators 3/4/5 are copied unchanged into both templates;
    prior VAR saves confirm separators 6/8 and CRLF. The default helper profile
    remains flat/scalar. Explicit allow_complex selects the 2026-11-01 ordinary
    root-comment template for identified nested and ARRAY member records;
    no dependent values or recursive business proof are produced.
    AutoShop V4.11.0.5 saves literal '=' and '#' inside member comments
    unchanged (INOUT probe, 2026-10-26). No escaping is inferred for other
    initializer delimiters; definition comments themselves are never rewritten.
    """
    if not allow_complex:
        definition = flat_scalar_definition(raw, name)
    else:
        definition = tables.parse(raw, 'stru')
        if definition.name != name or not definition.rows:
            raise BridgeError('Expected the exact nonempty structure definition.')
        for index, row in enumerate(definition.rows):
            scalar = descriptor(row.type_text or tables.TYPES.get(row.type_code))
            valid_scalar = (scalar is not None and scalar.code == row.type_code
                and (row.type_text == scalar.type_text if scalar.string_length is not None
                     else row.type_text in ('', scalar.canonical)))
            # Normal 2026-11-01 saves retain root comment slots for both
            # nested structures and ARRAY members, without dependent values.
            # This qualifies record identity, not recursive business semantics.
            valid_named = (row.type_code == 64 and row.type_text.isidentifier()
                           and scalar is None and row.type_text != 'ARRAY')
            valid_array = row.type_code == 128 and array_descriptor(row.type_text) is not None
            if not (valid_scalar or valid_named or valid_array):
                raise FormatRejection('Ordinary FB structure member profile is not implemented.',
                    code='offline_structure_member_unobserved',
                    context=dict(stage='fb_structure_member', structure=name, member=row.name,
                        member_index=index, field='data_type', index_base=0,
                        value=dict(type_code=row.type_code, type_text_raw=row.type_text),
                        reason='unobserved_member_descriptor'))
    for index, row in enumerate(definition.rows):
        _validate_member_comment(row, index, name)
    return comment_initializer((row.name, row.comment) for row in definition.rows)


def array_structure_initial(raw, name, dimensions, *, structure_definitions=None,
                            allow_nested=False, allow_recursive=False):
    """Observed value/comment defaults for ARRAYs of a concrete structure.

    Emit scalar members in original declaration order, including empty comment
    markers. Existing ARRAY members are omitted; separators still follow each
    emitted member's original position. This is not the comment-only template
    used for an ordinary structure variable, nor a recursive type proof.
    Explicit allow_nested plus exact supplied child bytes selects the observed
    one-level nested-value profile. Default callers retain the s28 strict scope.
    Explicit allow_recursive selects the separately observed recursive profile:
    nested comment markers exist only for nonempty comments, scalar markers
    always exist, and ARRAY members are omitted at every traversed level.
    """
    if (not isinstance(dimensions, (tuple, list)) or len(dimensions) not in (1, 2)
            or any(type(n) is not int or n <= 0 for n in dimensions)):
        raise BridgeError("Structure ARRAY dimensions require one/two positive integer counts.")
    shape = array_descriptor("{}[{}]".format(name, ",".join(map(str, dimensions))))
    if not isinstance(raw, bytes):
        raise BridgeError("Structure ARRAY default requires native structure definition bytes.")
    definition = tables.parse(raw, "stru")
    if definition.name != name or not definition.rows:
        raise BridgeError("Structure ARRAY requires the exact nonempty definition identity.")
    # Bound expansion while assembling it, before a repeated child can create
    # an oversized intermediate. 65533 is tables.string's existing UTF-8
    # CString ceiling, not a PLC/member-count limit. Reserve all wrappers now.
    prefix = "[{}((".format(shape.dimensions[-1])
    suffix = "))]"
    if len(shape.dimensions) == 2:
        prefix = "[{}".format(shape.dimensions[0]) + prefix
        suffix += "]"
    limit = min(MAX_NATIVE_SIZE, 65533)
    size = len(prefix.encode('utf-8')) + len(suffix.encode('utf-8'))
    if size > limit:
        raise BridgeError('Structure ARRAY initializer exceeds native text size limit.')
    parts = [prefix]

    def append(value):
        nonlocal size
        added = len(value.encode('utf-8'))
        if added > limit - size:
            raise BridgeError('Structure ARRAY initializer exceeds native text size limit.')
        parts.append(value)
        size += added

    defaults = {1: "OFF", 4: "0", 16: "0", 32: "0.000000", 2048: "",
                8192: "0", 4096: "192.168.1.0"}
    if allow_recursive:
        if not allow_nested:
            raise BridgeError('Recursive ARRAY defaults require explicit nested-profile selection.')
        # Iterative formatting avoids the Python recursion limit. Only code64
        # value dependencies are traversed, not a business type-use graph.
        # All emitted bytes share the wrapper-reserved budget above.
        active = {name}
        parsed_children = {}
        pending = [('member', definition, i) for i in reversed(range(len(definition.rows)))]
        while pending:
            kind, owner, index = pending.pop()
            if kind == 'close':
                append(owner)
                active.remove(index)
                continue
            row = owner.rows[index]
            separator = ', ' if index < len(owner.rows) - 1 else ''
            context = dict(stage=('fb_array_structure_initializer' if owner is definition
                                  else 'fb_recursive_array_structure_initializer'), structure=owner.name,
                member=row.name, member_index=index, field='data_type', index_base=0,
                value=dict(type_code=row.type_code, type_text_raw=row.type_text))
            if row.type_code == 128:
                if array_descriptor(row.type_text) is None:
                    raise FormatRejection('Omitted ARRAY member requires its actual ARRAY descriptor.',
                        code='offline_array_profile_unobserved',
                        context=dict(context, reason='member_default_unobserved'))
                continue
            if row.type_code == 64:
                valid_name = (row.type_text.isidentifier() and descriptor(row.type_text) is None
                              and row.type_text != 'ARRAY')
                child_raw = (structure_definitions.get(row.type_text)
                             if isinstance(structure_definitions, dict) else None)
                if not valid_name or not isinstance(child_raw, bytes):
                    raise FormatRejection('Recursive ARRAY default requires exact supplied child bytes.',
                        code='offline_array_profile_unobserved', context=dict(context,
                            reason='member_default_unobserved', definition_supplied=isinstance(child_raw, bytes),
                            requires='exact_nonempty_child_definition'))
                if row.type_text in active:
                    raise FormatRejection('Recursive ARRAY default contains a cyclic value dependency.',
                        code='offline_array_profile_unobserved',
                        context=dict(context, reason='recursive_default_cycle', child_structure=row.type_text))
                child = parsed_children.get(row.type_text)
                if child is None:
                    try:
                        child = tables.parse(child_raw, 'stru')
                    except BridgeError as exc:
                        raise FormatRejection('Recursive ARRAY child native definition is not recognized.',
                            code='offline_array_profile_unobserved', context=dict(context,
                                reason='child_definition_unrecognized', child_structure=row.type_text)) from exc
                    if child.name != row.type_text or not child.rows:
                        raise FormatRejection('Recursive ARRAY child identity must be exact and nonempty.',
                            code='offline_array_profile_unobserved',
                            context=dict(context, reason='exact_nonempty_child_definition_required'))
                    parsed_children[row.type_text] = child
                _validate_member_comment(row, index, owner.name, 'fb_recursive_array_structure_initializer')
                append(row.name + ':=(')
                active.add(child.name)
                pending.append(('close', ')' + ('\x07' + row.comment if row.comment else '') + separator, child.name))
                pending.extend(('member', child, i) for i in reversed(range(len(child.rows))))
                continue
            scalar = descriptor(row.type_text or tables.TYPES.get(row.type_code))
            valid_text = scalar is not None and (row.type_text == scalar.type_text
                if scalar.string_length is not None else row.type_text in ('', scalar.canonical))
            if scalar is None or scalar.code != row.type_code or not valid_text or scalar.code not in defaults:
                raise FormatRejection('Recursive ARRAY scalar default profile is not implemented.',
                    code='offline_array_profile_unobserved',
                    context=dict(context, reason='member_default_unobserved'))
            _validate_member_comment(row, index, owner.name, 'fb_recursive_array_structure_initializer')
            append(row.name + ':=' + defaults[scalar.code] + '\x07' + row.comment + separator)
        return ''.join(parts) + suffix
    for index, row in enumerate(definition.rows):
        if row.type_code == 128:
            continue  # Normal saved mixed definition omits ARRAY members.
        if row.type_code == 64 and allow_nested:
            definitions = {} if structure_definitions is None else structure_definitions
            valid_name = (row.type_text.isidentifier() and descriptor(row.type_text) is None
                          and row.type_text != 'ARRAY')
            child_raw = definitions.get(row.type_text) if isinstance(definitions, dict) else None
            if not valid_name or not isinstance(child_raw, bytes):
                raise FormatRejection('Nested ARRAY default requires an exact supplied child definition.',
                    code='offline_array_profile_unobserved',
                    context=dict(stage='fb_array_structure_initializer', structure=name, member=row.name,
                        member_index=index, field='data_type', index_base=0,
                        value=dict(type_code=row.type_code, type_text_raw=row.type_text),
                        reason='member_default_unobserved', definition_supplied=isinstance(child_raw, bytes),
                        requires='exact_flat_scalar_child_definition'))
            try:
                # Explicitly one nested level. Never recurse into another
                # code64 or ARRAY child, nor qualify structure-rename callers
                # which retain this helper's default strict profile.
                child = flat_scalar_definition(child_raw, row.type_text)
            except BridgeError as exc:
                raise FormatRejection('Nested ARRAY child default profile is not implemented.',
                    code='offline_array_profile_unobserved',
                    context=dict(stage='fb_nested_array_structure_initializer', structure=name,
                        member=row.name, member_index=index, field='data_type', index_base=0,
                        value=dict(type_code=row.type_code, type_text_raw=row.type_text),
                        child_structure=row.type_text, reason='child_default_profile_unobserved',
                        child_diagnostic=getattr(exc, 'context', None))) from exc
            append(row.name + ':=(')
            for child_index, child_row in enumerate(child.rows):
                if child_row.type_code not in defaults:
                    raise FormatRejection('Nested child scalar default is not implemented.',
                        code='offline_array_profile_unobserved',
                        context=dict(stage='fb_nested_array_structure_initializer',
                            structure=child.name, member=child_row.name, member_index=child_index,
                            field='data_type', index_base=0,
                            value=dict(type_code=child_row.type_code, type_text_raw=child_row.type_text),
                            reason='member_default_unobserved', parent_structure=name,
                            parent_member=row.name))
                _validate_member_comment(child_row, child_index, child.name,
                                         'fb_nested_array_structure_initializer')
                append(child_row.name + ':=' + defaults[child_row.type_code] + '\x07'
                       + child_row.comment + (', ' if child_index < len(child.rows) - 1 else ''))
            _validate_member_comment(row, index, name, 'fb_array_structure_initializer')
            append(')\x07' + row.comment + (', ' if index < len(definition.rows) - 1 else ''))
            continue
        scalar = descriptor(row.type_text or tables.TYPES.get(row.type_code))
        valid_text = scalar is not None and (row.type_text == scalar.type_text
            if scalar.string_length is not None else row.type_text in ("", scalar.canonical))
        if scalar is None or scalar.code != row.type_code or not valid_text or scalar.code not in defaults:
            raise FormatRejection(
                "Structure ARRAY member default profile is not implemented.",
                code="offline_array_profile_unobserved",
                context=dict(stage="fb_array_structure_initializer", structure=name,
                             member=row.name, member_index=index, field="data_type",
                             value=dict(type_code=row.type_code, type_text_raw=row.type_text),
                             index_base=0, reason="member_default_unobserved", requires="independent_ide_sample"),
            )
        _validate_member_comment(row, index, name, "fb_array_structure_initializer")
        append(row.name + ":=" + defaults[scalar.code] + "\x07" + row.comment
               + (", " if index < len(definition.rows) - 1 else ""))
    return ''.join(parts) + suffix


def _record(op, definitions):
    dtype, category = op["data_type"], op["category"]
    _text(dtype)
    if not isinstance(dtype, str) or not isinstance(category, str) or category not in fb.CATEGORIES.values():
        raise BridgeError("Unsupported FB type/category.")
    scalar = descriptor(dtype)
    code, type_text = (scalar.code, scalar.type_text) if scalar else (None, "")
    initial = op["initial_value"]
    try:
        array = array_descriptor(dtype) if scalar is None else None
    except FormatRejection as exc:
        exc.context.update(variable=op["name"], category=category)
        raise
    if array is not None:
        element = descriptor(array.element_type)
        if element is not None and element.code not in ARRAY_ELEMENT_CODES:
            raise FormatRejection(
                "FB ARRAY element profile needs a normal IDE save.",
                code="offline_array_profile_unobserved",
                context=dict(stage="fb_array_initializer", variable=op["name"],
                             data_type=dtype, category=category, field="element_type",
                             value=array.element_type, dimensions=list(array.dimensions),
                             definition_supplied=array.element_type in definitions,
                             reason="scalar_element_profile_unobserved",
                             requires="independent_ide_sample"),
            )
        if element is None or element.code not in ARRAY_ELEMENT_CODES:
            if array.element_type not in definitions:
                raise FormatRejection(
                    "FB ARRAY requires an exact structure definition for the named element.",
                    code="offline_array_profile_unobserved",
                    context=dict(stage="fb_array_initializer", variable=op["name"],
                                 data_type=dtype, category=category, field="element_type",
                                 value=array.element_type, dimensions=list(array.dimensions),
                                 definition_supplied=False, reason="element_definition_required"),
                )
            try:
                array_initial = array_structure_initial(definitions[array.element_type], array.element_type,
                    array.dimensions, structure_definitions=definitions, allow_nested=True, allow_recursive=True)
            except FormatRejection as exc:
                exc.context.update(variable=op["name"], data_type=dtype, category=category, definition_supplied=True)
                raise
            except BridgeError as exc:
                raise FormatRejection(str(exc), code="offline_array_profile_unobserved",
                    context=dict(stage="fb_array_initializer", variable=op["name"],
                                 data_type=dtype, category=category, field="element_type",
                                 value=array.element_type, definition_supplied=True,
                                 reason="exact_structure_definition_required")) from exc
        else:
            array_initial = ""
        if initial is not None:
            raise FormatRejection(
                "FB ARRAY additions require initial_value=null for the observed IDE default.",
                code="offline_array_initial_value_unobserved",
                context=dict(stage="fb_array_initializer", variable=op["name"],
                             data_type=dtype, category=category, field="initial_value",
                             value=initial, reason="explicit_array_initializer_unobserved"),
            )
        if "type_kind" in op:
            raise BridgeError("Explicit function_block kind conflicts with an ARRAY type.")
        # Normal numeric/BYTE/IP and INT[3,2] saves: the declaration CString
        # contains its dimensions, code is 128, and native default is empty.
        # They use the same four-tail record. No element
        # values, addresses or a named-element default are synthesized here.
        code, type_text, initial = array.code, array.type_text, array_initial
    elif code is None:
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
                initial = flat_structure_initial(definitions[dtype], dtype, allow_complex=True)
            except FormatRejection as exc:
                exc.context.update(variable=op["name"], category=category)
                raise
    elif "type_kind" in op:
        raise BridgeError("Explicit function_block kind conflicts with a scalar type.")
    elif category == "INOUT":
        if initial is not None:
            raise BridgeError("INOUT requires a null independent initializer.")
        initial = {1: "OFF", 4: "0", 16: "0", 32: "0.000000", 2048: "",
                   8192: "0", 4096: "192.168.1.0"}[code]
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
