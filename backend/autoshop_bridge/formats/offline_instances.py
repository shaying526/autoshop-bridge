"""Qualified FBI append candidates; never construct archives or allocate memory."""

import struct

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import empty_table, fb, instances, tables
from autoshop_bridge.formats.offline_variables import _text
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
            "FBI additions require the observed paired-table archive layout.",
            code="offline_unsupported_fbi_layout",
            context=dict(field="opaque_container", profile=PROFILE,
                         record_segment_offset=start, record_segment_bytes=end-start),
        )
    return document, start, end


def rebuild(raw, operations, definitions=None):
    """Append default project-FB records, preserving every old/opaque byte.

    Definitions are exact registered LiteST FB bytes, frozen by the caller.
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
            definition = fb.parse(definitions[op["data_type"]])
            if definition.program_name != op["data_type"]:
                raise BridgeError("Project FB definition identity differs.")
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
