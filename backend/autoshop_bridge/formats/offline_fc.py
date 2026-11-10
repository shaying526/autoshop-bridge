"""Independent FC additions and observed existing numeric/category fields.

Unrequested records/fields and the entire embedded ST object are preserved bytes.
The workflow owns registration, closed-project checks, backups and readback.
"""

import struct

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import fc, tables
from autoshop_bridge.formats.array_types import descriptor as array_descriptor, structure_element
from autoshop_bridge.formats.scalar_types import descriptor, ARRAY_ELEMENT_CODES
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.projects.identifiers import precheck_addition_names

PROFILE = "fc-scalar-add-unallocated-v1"
SCALARS = {"BOOL": 1, "INT": 4, "DINT": 16, "REAL": 32, "BYTE": 8192, "IP": 4096}
CATEGORIES = {"VAR": 0, "IN": 1, "OUT": 2, "INOUT": 3}
NUMERIC_SCALARS = {"BOOL": 1, "INT": 4, "DINT": 16, "REAL": 32}


def _set_existing(raw, operation):
    """Patch only one observed DWORD; preserve every other native byte."""
    if (set(operation) != {"op", "name", "field", "expected", "value"}
            or operation["field"] not in ("category", "data_type")
            or any(not isinstance(operation[key], str) for key in ("name", "expected", "value"))):
        raise BridgeError("FC set supports explicit category or numeric data_type fields only.")
    obj = fc.parse(raw)
    matches = [v for v in obj.variables if v.name == operation["name"]]
    if len(matches) != 1:
        raise BridgeError("FC set requires one exact existing declaration name.")
    variable = matches[0]
    numeric = {value: key for key, value in NUMERIC_SCALARS.items()}
    if (variable.type_text != "" or variable.type_code not in numeric
            or variable.fields[0] not in CATEGORIES.values()):
        raise BridgeError("Existing FC field changes require an observed empty-CString numeric scalar record.")
    if operation["field"] == "category":
        old = {value: key for key, value in CATEGORIES.items()}[variable.fields[0]]
        values = CATEGORIES
        offset = variable.end - 12
    else:
        old = numeric[variable.type_code]
        values = NUMERIC_SCALARS
        reader = fc.Reader(raw, variable.offset, variable.end)
        reader.string()
        offset = reader.pos
    if operation["expected"] != old or operation["value"] not in values:
        raise BridgeError("FC field baseline differs or requested numeric/category value is unsupported.")
    result = raw[:offset] + struct.pack("<I", values[operation["value"]]) + raw[offset + 4:]
    after = fc.parse(result)
    if after.source != obj.source or len(after.variables) != len(obj.variables):
        raise BridgeError("FC existing-field candidate changed body/count.")
    return result


def _text(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise BridgeError("FC declaration requires text without control characters.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise BridgeError("Invalid Unicode in FC declaration.") from exc
    if size > 4096:
        raise BridgeError("FC declaration text exceeds size limit.")


def rebuild(raw, operations, structure_definitions=None):
    """Apply 1..32 explicit additions or observed existing numeric-field changes.

    New records use the observed category/FFFFFFFF/0 tail. These are not
    borrowed addresses or an interpretation of arbitrary existing tail fields.
    Empty, compact and stale-line-table bodies are preserved without rebuilding.
    """
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit FC additions.")
    if any(isinstance(op, dict) and op.get("op") == "set" for op in operations):
        original_names = {v.name for v in fc.parse(raw).variables}
        result = raw
        for operation in operations:
            if not isinstance(operation, dict):
                raise BridgeError("FC operation must be an object.")
            if operation.get("op") == "set":
                if not isinstance(operation.get("name"), str) or operation["name"] not in original_names:
                    raise BridgeError("FC set targets an existing input declaration, not a newly appended row.")
                result = _set_existing(result, operation)
            else:
                result = rebuild(result, [operation], structure_definitions)
        return result
    before = fc.parse(raw)
    definitions = {} if structure_definitions is None else structure_definitions
    if not isinstance(definitions, dict):
        raise BridgeError("ARRAY element definitions must map exact names to native bytes.")
    names = {v.name.casefold() for v in before.variables}
    encoded = []
    for operation_index, op in enumerate(operations):
        if (not isinstance(op, dict)
                or set(op) != {"op", "name", "data_type", "category", "initial_value", "comment"}
                or op["op"] != "add"):
            raise BridgeError("Offline FC supports exact scalar/ARRAY/structure-root add fields only.")
        for key in ("name", "data_type", "category", "comment"):
            _text(op[key])
        scalar = descriptor(op["data_type"])
        try:
            array = array_descriptor(op["data_type"]) if scalar is None else None
        except FormatRejection as exc:
            exc.context.update(variable=op["name"], category=op["category"], operation_index=operation_index)
            raise
        if array is not None:
            element = descriptor(array.element_type)
            if element is not None and element.code not in ARRAY_ELEMENT_CODES:
                raise FormatRejection("FC ARRAY element profile needs a normal IDE save.",
                    code="offline_array_profile_unobserved",
                    context=dict(stage="fc_array_addition", data_type=op["data_type"],
                                 field="element_type", value=array.element_type,
                                 requires="independent_ide_sample"))
            if element is None:
                try:
                    structure_element(array.element_type, definitions)
                except FormatRejection as exc:
                    exc.context.update(variable=op["name"], data_type=op["data_type"],
                                       category=op["category"], operation_index=operation_index)
                    raise
        native_type = scalar or array
        if native_type is None:
            # Ordinary FC records store an exact registered root, not FB-style
            # initializer/retention fields or serialized child defaults.
            tables.registered_structure_definition(op["data_type"], definitions)
            native_type = tables.RegisteredStructureDescriptor(op["data_type"])
        if (not tables.identifier(op["name"]) or op["name"].casefold() in names
                or native_type is None or op["category"] not in CATEGORIES
                or op["initial_value"] is not None):
            raise BridgeError("FC additions require unique supported scalar/ARRAY/structure-root declarations and initial_value=null.")
        precheck_addition_names(dict(schema=1, operations=[op]))
        names.add(op["name"].casefold())
        encoded.append(tables.string(native_type.type_text) + struct.pack("<I", native_type.code)
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
