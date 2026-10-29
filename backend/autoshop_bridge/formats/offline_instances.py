"""Qualified FBI add/set candidates; preserve archives and existing metadata."""

import struct
from itertools import groupby

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import empty_table, fb, instances, tables
from autoshop_bridge.formats.offline_variables import _text, instance_definition
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.projects.identifiers import precheck_addition_names

PROFILE = "fbi-project-fb-unallocated-append-v1"


def _layout(raw):
    try:
        document = instances.parse(raw)
    except BridgeError as exc:
        raise FormatRejection(str(exc), code="offline_unsupported_fbi_layout",
                              context=dict(field="instance_segment", profile=PROFILE,
                                           original_error=str(exc))) from exc
    start = document["record_segment_offset"]
    end = start + document["record_segment_bytes"]
    # The read-only parser intentionally accepts opaque archives. Append is
    # narrower: removing declarations must reveal the fully observed pair of
    # empty tables with shared CArchive state. No archive bytes are generated.
    empty = raw[:start] + struct.pack("<I", 0) + raw[end:]
    if empty_table.instance_segment(empty) != (start, start + 4):
        raise FormatRejection(
            "FBI mutations require the observed paired-table archive layout.",
            code="offline_unsupported_fbi_layout",
            context=dict(field="opaque_container", profile=PROFILE,
                         record_segment_offset=start, record_segment_bytes=end-start),
        )
    return document, start, end


def _append(raw, operations, definitions=None):
    """Append default FB records, preserving every old/opaque byte.

    Definitions are registered LiteST bytes or explicit LD/library descriptors.
    Empty initialization is independent of the referenced interface or body;
    the IDE/compiler owns all allocation and business/reference validation.
    """
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit FBI instance additions.")
    definitions = {} if definitions is None else definitions
    if not isinstance(definitions, dict):
        raise BridgeError("Expected exact project FB name/bytes definitions.")
    try:
        precheck_addition_names(dict(operations=operations))
    except UnicodeError as exc:
        raise BridgeError("Invalid Unicode in FBI declaration.") from exc
    before, start, end = _layout(raw)
    names = {r["name"].casefold() for r in before["instances"]}
    encoded = []
    for index, op in enumerate(operations):
        if (not isinstance(op, dict) or op.get("op") != "add"
                or set(op) != {"op", "name", "data_type", "initial_value", "comment"}):
            raise BridgeError("FBI add requires exact name/data_type/initial_value/comment fields.")
        for key in ("name", "data_type", "comment"):
            _text(op[key])
        if (not tables.identifier(op["name"]) or op["name"].casefold() in names
                or len(names) >= 4096):
            raise BridgeError("Invalid/duplicate FBI name or instance limit exceeded.")
        context = dict(operation_index=index, variable=op["name"], data_type=op["data_type"])
        if op["initial_value"] is not None:
            raise FormatRejection("FBI additions require initial_value=null (native defaults).",
                                  code="offline_unsupported_fbi_initializer",
                                  context=dict(context, field="initial_value"))
        try:
            if op["data_type"] not in definitions:
                raise BridgeError("Expected an exact registered project FB definition.")
            instance_definition(op["data_type"], definitions[op["data_type"]])
        except BridgeError as exc:
            raise FormatRejection(str(exc), code="offline_unsupported_fb_instance",
                                  context=dict(context, field="data_type")) from exc
        names.add(op["name"].casefold())
        # Observed FBI defaults differ from FB-local variables: flags=0 and
        # exact selector type text, not VAR/retention fields or uppercase text.
        encoded.append(struct.pack("<II", 256, 256) + tables.string(op["name"])
                       + tables.string("") + struct.pack("<II", 0, 0xFFFFFFFF)
                       + tables.string(op["comment"]) + b"\xff\xfe\xff\0"
                       + struct.pack("<II", 0, 0) + tables.string(op["data_type"])
                       + b"\xff" * 8)
    result = (raw[:start] + struct.pack("<I", len(names)) + raw[start+4:end]
              + b"".join(encoded) + raw[end:])
    if len(result) > MAX_NATIVE_SIZE:
        raise BridgeError("FBI candidate exceeds size limit.")
    after, new_start, new_end = _layout(result)
    if (new_start != start or result[:start] != raw[:start]
            or result[new_end:] != raw[end:]
            or [r["name"] for r in after["instances"]] != [r["name"] for r in before["instances"]] + [op["name"] for op in operations]):
        raise BridgeError("FBI candidate failed envelope/order verification.")
    for old, new in zip(before["instances"], after["instances"]):
        a, b = old["record_offset"], new["record_offset"]
        if raw[a:a+old["record_bytes"]] != result[b:b+new["record_bytes"]]:
            raise BridgeError("FBI candidate changed an existing instance record.")
    return result


def field_values(raw, row):
    """Exact native string fields/spans in one already parsed instance record."""
    reader = fb.Reader(raw, row["record_offset"], row["record_offset"] + row["record_bytes"])
    if (reader.u32(), reader.u32()) != (256, 256):
        raise BridgeError("Unsupported FBI field descriptor.")
    spans = {}
    for field in ("name", "initial_value"):
        start = reader.pos
        value = reader.string()
        spans[field] = (start, reader.pos, value)
    reader.take(8)  # Existing flags/address remain uninterpreted bytes.
    start = reader.pos
    value = reader.string()
    spans["comment"] = (start, reader.pos, value)
    return spans


def _field_text(value, field):
    if not isinstance(value, str):
        raise BridgeError("FBI field values must be explicit strings; clear with an empty string.")
    try:
        return tables.string(value)
    except (UnicodeError, BridgeError) as exc:
        raise FormatRejection(str(exc), code="offline_unsupported_fbi_field_text",
                              context=dict(field=field, representation="native_utf8_carchive_string")) from exc


def edit_fields(raw, operations):
    """Replace requested native strings only; no initializer grammar/semantics.

    Initializers can include the native control separators and nested contents.
    No dependency, reference or business validation is performed. The native
    string encoder and full parser enforce representation/identity boundaries.
    """
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit FBI field edits.")
    before, start, end = _layout(raw)
    rows = before["instances"]
    records = [raw[r["record_offset"]:r["record_offset"]+r["record_bytes"]] for r in rows]
    values = [dict(name=r["name"], comment=r["comment"], initial_value=r["initial_value_raw"]) for r in rows]
    for index, op in enumerate(operations):
        if (not isinstance(op, dict) or set(op) != {"op", "name", "field", "expected", "value"}
                or op.get("op") != "set" or op.get("field") not in ("name", "comment", "initial_value")):
            raise BridgeError("FBI set requires exact name/field/expected/value; fields: name, comment, initial_value.")
        matches = [i for i, value in enumerate(values) if value["name"] == op["name"]]
        if len(matches) != 1:
            raise BridgeError("FBI set requires one exact current instance name.")
        i = matches[0]
        field = op["field"]
        old = values[i][field]
        if not isinstance(op["expected"], str) or op["expected"] != old:
            raise FormatRejection("FBI field baseline differs: {}.{}".format(op["name"], field),
                                  code="offline_conflict", context=dict(variable=op["name"], field=field,
                                                                        operation_index=index))
        encoded = _field_text(op["value"], field)
        if field == "name" and (not op["value"].isidentifier() or any(
                j != i and v["name"].casefold() == op["value"].casefold() for j, v in enumerate(values))):
            raise BridgeError("Invalid/duplicate native FBI instance name.")
        if old == op["value"]:
            continue
        local_row = dict(rows[i], record_offset=0, record_bytes=len(records[i]))
        a, b, actual = field_values(records[i], local_row)[field]
        if actual != old:
            raise BridgeError("FBI field plan and current record differ.")
        records[i] = records[i][:a] + encoded + records[i][b:]
        values[i][field] = op["value"]
    result = raw[:start+4] + b"".join(records) + raw[end:]
    if len(result) > MAX_NATIVE_SIZE:
        raise BridgeError("FBI field candidate exceeds size limit.")
    after, new_start, new_end = _layout(result)
    if new_start != start or result[:start+4] != raw[:start+4] or result[new_end:] != raw[end:]:
        raise BridgeError("FBI field candidate changed its count or opaque containers.")
    for old, new, expected, record in zip(rows, after["instances"], values, records):
        if (new["name"] != expected["name"] or new["comment"] != expected["comment"]
                or new["initial_value_raw"] != expected["initial_value"]
                or any(new[k] != old[k] for k in ("data_type", "type_text_raw", "type_code", "display_order", "uninterpreted_metadata"))
                or result[new["record_offset"]:new["record_offset"]+new["record_bytes"]] != record):
            raise BridgeError("FBI field candidate failed complete record verification.")
    return result


def rebuild(raw, operations, definitions=None):
    """Sequential add/set groups, preserving s18 append behavior and old bytes."""
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit FBI operations.")
    if any(not isinstance(op, dict) or op.get("op") not in ("add", "set") for op in operations):
        raise BridgeError("FBI supports explicit add/set; deletion uses the existing separate request.")
    result = raw
    for kind, group in groupby(operations, key=lambda op: op["op"]):
        batch = list(group)
        result = _append(result, batch, definitions) if kind == "add" else edit_fields(result, batch)
    return result
