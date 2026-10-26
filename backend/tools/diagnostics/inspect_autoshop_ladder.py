"""Experimental, file-only LD/LD FB record inspection; not a logic interpreter.

Observed framing is checked to EOF, including reciprocal pin membership. Raw
element/layout fields remain uninterpreted. This separate read-only entry does
not change scan, service, source export or the existing editing adapters.
"""

import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.fb import Reader, variable_tables
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE, MAX_PROGRAM_LINES, validate_text

PROFILE = "experimental-ld-fb-record-inspection-v1"
MAX_RECORDS = 4096
MAX_PREFIX = 256 * 1024
ELEMENT_FIELDS = struct.Struct("<IIHIIHIIIIII")
# Kinds 2/3 were added only after the user's saved edge-contact probe and
# screenshot matched the same bounded record framing. Unknown kinds still fail.
OBSERVED_KINDS = {0, 1, 2, 3, 5, 6, 7, 8, 10, 11, 14, 15, 17}


def require(condition, message):
    if not condition:
        raise BridgeError("Unsupported ladder inspection layout: " + message)


def u16(reader):
    return struct.unpack("<H", reader.take(2))[0]


def array(reader, maximum=MAX_RECORDS):
    count = reader.u32()
    require(count <= maximum, "array count exceeds inspection limit")
    return [reader.u32() for _ in range(count)]


def columns(raw, start, end, *, shared_class):
    """Recognize the observed CLVTItem list, independent of header offsets."""
    reader = Reader(raw, start, end)
    require(u16(reader) == 4, "unobserved column list")
    known = shared_class
    for _ in range(4):
        tag = u16(reader)
        if tag == 65535:
            require(not known and u16(reader) == 1, "unobserved class schema")
            size = u16(reader)
            require(size == 8 and reader.take(size) == b"CLVTItem", "unknown class")
            known = True
        else:
            require(tag == 32769 and known, "undefined column class reference")
        # Fifteen observed bytes per item; their UI semantics are not decoded.
        reader.take(15)
    return reader.pos


def column_starts(raw, begin, end):
    require(end - begin <= MAX_PREFIX, "metadata prefix exceeds inspection limit")
    pattern = rb"\x04\x00(?:\xff\xff|\x01\x80)"
    matches = list(re.finditer(pattern, raw[begin:end]))
    require(len(matches) <= 16, "too many metadata candidates")
    return [begin + item.start() for item in matches]


def block_document(reader, *, instance=False, _readonly_clipboard_unconfigured=False):
    version, enable_label = reader.string(), reader.string()
    instance_name = reader.string() if instance else None
    require(not instance or instance_name.isidentifier()
            or (_readonly_clipboard_unconfigured is True and instance_name == "???"),
            "invalid instance name")
    inputs, outputs, count = u16(reader), u16(reader), u16(reader)
    total = inputs + outputs
    require(total <= 256 and count == 1 + 2 * total, "unknown block pin layout")
    values = [reader.string() for _ in range(count)]
    require(values[0].isidentifier(), "invalid block name")
    pins = []
    for actual, descriptor in zip(values[1:1 + total], values[1 + total:]):
        parts = descriptor.split("|")
        require(len(parts) == 3 and parts[0].isidentifier(), "unknown pin descriptor")
        require(parts[1] == "1" and parts[2] in (("0", "1", "2") if instance else ("0", "1")),
                "unknown pin flags")
        pins.append({"name": parts[0], "actual": actual,
                     "direction_code": int(parts[2]), "descriptor_raw": descriptor})
    require(sum(p["direction_code"] in (0, 2) for p in pins) == inputs,
            "block input count differs from descriptors")
    result = {"name": values[0], "version_raw": version,
            "enable_label": enable_label, "input_count": inputs,
            "output_count": outputs, "pins": pins}
    if instance:
        result["instance_name"] = instance_name
    return result


def execution_document(reader, text, *, clipboard=False):
    """Observed EXECUTE extension: plaintext CString and indexed row records.

    This is independent of the transformed standalone ST payload. Empty live
    clipboard blocks were observed with zero rows; that exception is not applied
    to a saved native file without a matching saved sample.
    """
    layout = struct.unpack("<2I", reader.take(8))
    reference, source = reader.string(), reader.string()
    require(re.fullmatch(r"_STB(?:-1|[0-9]+)", reference) is not None
            and text == "EXECUTE " + reference, "execution reference differs from element")
    encoded = source.encode("utf-8")
    validate_text(encoded)
    lines = source.count("\n") + 1
    count = reader.u32()
    empty_clipboard = clipboard and source == "" and count == 0
    require(empty_clipboard or 1 <= count == lines <= MAX_PROGRAM_LINES,
            "execution source/line-table count mismatch or limit")
    rows = [struct.unpack("<4I", reader.take(16)) for _ in range(count)]
    require(all(row[0] == i for i, row in enumerate(rows)), "execution row indices")
    return {"reference": reference, "source": source,
            "source_sha256": hashlib.sha256(encoded).hexdigest(),
            "source_line_count": lines, "line_table_count": count,
            "line_table_rows_raw": [list(row) for row in rows],
            "layout_fields_raw": list(layout)}


def element_record(reader, *, clipboard=False, _readonly_clipboard_unconfigured=False):
    """Shared observed node framing; clipboard omits the leading duplicate ID."""
    require(type(_readonly_clipboard_unconfigured) is bool
            and (not _readonly_clipboard_unconfigured or clipboard is True),
            "unconfigured call exception is clipboard-readonly only")
    offset = reader.pos
    prefix = reader.take(ELEMENT_FIELDS.size - (4 if clipboard else 0))
    fields = ELEMENT_FIELDS.unpack(b"\0" * 4 + prefix if clipboard else prefix)
    if clipboard:
        fields = (fields[6],) + fields[1:]
    identity, kind = fields[:2]
    require(kind in OBSERVED_KINDS, "unobserved element kind {}".format(kind))
    require(identity == fields[6], "element identity mismatch")
    layout_u16, text = u16(reader), reader.string()
    tail = struct.unpack("<5I", reader.take(20))
    require(tail[0] == kind and tail[3] == 0, "element tail mismatch")
    # Project FB calls carry an observed reference field where ordinary records
    # have UINT32_MAX. Preserve it verbatim; its meaning is not inferred.
    require(kind == 15 or tail[2] == 4294967295, "element tail mismatch")
    require(tail[4] == (kind if kind in (14, 15, 17) else 9999), "unobserved element tail")
    node = {"id": identity, "kind_raw": kind, "layout_u16_raw": layout_u16,
            "column_raw": fields[3], "row_raw": fields[4], "text": text,
            "left_connection": fields[10], "right_connection": fields[11],
            "prefix_fields_raw": list(fields), "tail_fields_raw": list(tail),
            "record_offset": offset}
    if kind in (14, 15):
        node["block"] = block_document(
            reader, instance=kind == 15,
            _readonly_clipboard_unconfigured=_readonly_clipboard_unconfigured)
    if kind == 17:
        node["embedded_st"] = execution_document(reader, text, clipboard=clipboard)
    node["record_end"] = reader.pos
    return node


def body(raw, start, end, *, auxiliary_rows=False):
    reader = Reader(raw, start, end)
    count = u16(reader)
    require(0 < count <= MAX_RECORDS, "element count outside inspection limit")
    elements = []
    by_id = {}
    for _ in range(count):
        node = element_record(reader)
        identity = node["id"]
        require(identity not in by_id, "element identity mismatch")
        elements.append(node)
        by_id[identity] = node

    graph_count = reader.u32()
    require(graph_count <= MAX_RECORDS * 2, "too many connection records")
    connections = []
    by_connection = {}
    for _ in range(graph_count):
        identity = reader.u32()
        left, right, flag = array(reader), array(reader), u16(reader)
        require(identity not in by_connection and flag == 0, "connection identity/flag")
        require(len(set(left)) == len(left) and len(set(right)) == len(right),
                "duplicate connection membership")
        for key, members in (("left_connection", left), ("right_connection", right)):
            require(all(item in by_id and by_id[item][key] == identity for item in members),
                    "connection references disagree with elements")
        group = {"id": identity, "left_elements": left,
                 "right_elements": right, "flag_raw": flag}
        connections.append(group)
        by_connection[identity] = group

    require(u16(reader) == 0, "unknown post-connection field")
    row_extent, next_connection = reader.u32(), reader.u32()
    network_count = reader.u32()
    require(0 < network_count <= MAX_RECORDS, "network marker count")
    rows = [u16(reader) for _ in range(network_count)]
    require(rows == sorted(set(rows)) and rows[0] == 0 and rows[-1] < row_extent,
            "network marker ordering")
    auxiliary_count = reader.u32()
    require(auxiliary_count <= MAX_RECORDS and (auxiliary_rows or auxiliary_count == 0),
            "unknown pre-mapping field")
    auxiliary = [u16(reader) for _ in range(auxiliary_count)]
    require(auxiliary == sorted(set(auxiliary)) and all(row < row_extent for row in auxiliary),
            "invalid auxiliary row list")
    require(reader.u32() == count, "element mapping count")
    mappings = {}
    for _ in range(count):
        identity, value = reader.u32(), reader.u32()
        require(identity in by_id and identity not in mappings, "element mapping identity")
        mappings[identity] = value
    require(reader.pos == end, "unconsumed bytes after diagram records")

    missing = []
    for node in elements:
        for field, members in (("left_connection", "left_elements"),
                               ("right_connection", "right_elements")):
            key = node[field]
            group = by_connection.get(key, {})
            if node["id"] not in group.get(members, []):
                # Comments and observed kind-8 empty drawing records have no
                # electrical membership. Do not invent links from coordinates.
                require(key == 0 and node["kind_raw"] in (8, 11),
                        "missing reciprocal connection membership")
                missing.append({"element": node["id"], "side": field})
        require(node["row_raw"] < row_extent, "element outside row extent")
        node["mapping_value_raw"] = mappings[node["id"]]
        node["network_marker_ordinal"] = bisect.bisect_right(rows, node["row_raw"])

    networks = []
    for ordinal, row in enumerate(rows, 1):
        members = [n for n in elements if n["network_marker_ordinal"] == ordinal]
        comments = [n for n in members if n["kind_raw"] == 11 and n["row_raw"] == row]
        require(len(comments) == 1, "network marker has no unique comment record")
        active = sum(n["kind_raw"] != 11 for n in members)
        networks.append({"marker_ordinal": ordinal, "row_raw": row,
                         "title": comments[0]["text"], "element_count": len(members),
                         "non_comment_element_count": active,
                         "only_comment_records": active == 0})
    result = {"elements": elements, "connections": connections, "networks": networks,
            "row_extent_raw": row_extent, "next_connection_raw": next_connection,
            "unlinked_drawing_sides": missing}
    if auxiliary_rows:
        result["pre_mapping_rows_raw"] = auxiliary
    return result


def inspect_bytes(raw):
    require(len(raw) <= MAX_NATIVE_SIZE and raw.startswith(b"AutoShop") and
            raw.endswith(b"\0" * 4), "not an observed FB envelope")
    offsets = [m.start() for m in re.finditer(b"AutoShop", raw) if m.start() > 0]
    require(len(offsets) <= 16, "too many embedded object candidates")
    found = []
    for inner in offsets:
        if inner > MAX_PREFIX or raw[inner - 4:inner] != b"\0" * 4:
            continue
        variables = list(variable_tables(raw, inner - 4))
        for variable_start, name, records in variables:
            outer = []
            for c in column_starts(raw, 8, variable_start):
                try:
                    if columns(raw, c, variable_start, shared_class=False) == variable_start:
                        outer.append(c)
                except BridgeError:
                    continue
            if len(outer) != 1:
                continue
            # Only the bounded metadata prefix is searched. All body/connection
            # boundaries thereafter follow counts, never text/sentinel searches.
            search_end = min(inner + MAX_PREFIX, len(raw) - 4)
            for c in column_starts(raw, inner + 8, search_end):
                try:
                    start = columns(raw, c, len(raw) - 4, shared_class=True)
                    result = body(raw, start, len(raw) - 4)
                except BridgeError:
                    continue
                found.append((name, records, result))
                require(len(found) == 1, "ambiguous embedded diagram")
    require(len(found) == 1, "no unique complete LD FB record match")
    name, records, result = found[0]
    result.update({"schema": 1, "status": "ladder_fb_inspected_experimental",
                   "read_only": True, "profile": PROFILE, "program_name": name,
                   "native_sha256": hashlib.sha256(raw).hexdigest(),
                   "variables": [v.as_dict(i) for i, v in enumerate(records)],
                   "coverage": "observed_record_structure_only",
                   "logic_semantics_verified": False,
                   "limitations": [
                       "Only the observed LD FB record layout is inspected; unknown layouts fail.",
                       "Raw element kinds, the layout uint16, drawing flags and mapping values are not interpreted.",
                       "Network marker ordinals are not a claim about IDE numbering or visibility.",
                       "No ST/IL conversion, Boolean expression synthesis, simulation or write-back.",
                       "Reads saved native bytes only; does not include unsaved editor content.",
                       "Separate experimental read-only entry; not the default scan or public service API.",
                   ]})
    return result


def inspect_program_bytes(raw):
    """Standalone LD container: one column archive then a diagram ending at EOF.

    No FB variable shell or FB trailing sentinel is assumed. Prefix fields are
    opaque; a unique structurally complete body is required within a bounded scan.
    """
    require(8 < len(raw) <= MAX_NATIVE_SIZE and raw.startswith(b"AutoShop"),
            "not an observed LD program envelope")
    found = []
    for candidate in column_starts(raw, 8, min(len(raw), MAX_PREFIX)):
        try:
            start = columns(raw, candidate, len(raw), shared_class=False)
            result = body(raw, start, len(raw), auxiliary_rows=True)
        except BridgeError:
            continue
        found.append(result)
    require(len(found) == 1, "no unique complete LD program record match")
    result = found[0]
    result.update(schema=1, status="ladder_program_inspected_experimental", read_only=True,
                  profile="experimental-ld-program-record-inspection-v1", program_name=None,
                  native_sha256=hashlib.sha256(raw).hexdigest(), variables=None,
                  coverage="observed_record_structure_only", logic_semantics_verified=False,
                  limitations=[
                      "Only the observed standalone LD program archive is inspected; prefix semantics remain opaque.",
                      "Local variable definitions are not supplied by this diagram container; null is not an empty table.",
                      "Raw layout/reference fields are retained, not interpreted as execution order or instructions.",
                      "Embedded ST is inspected only in its observed counted record layout; no ST/IL conversion, simulation or write-back.",
                      "Reads saved native bytes only; does not include unsaved editor content.",
                      "Separate experimental read-only entry; not the default scan or public service API.",
                  ])
    return result


def project_result(document, section="summary", network=1, offset=0, limit=20):
    require(0 <= offset and 1 <= limit <= 100, "invalid pagination")
    summary = {"variable_count": len(document["variables"]) if document["variables"] is not None else None,
               "element_count": len(document["elements"]),
               "connection_count": len(document["connections"]),
               "network_marker_count": len(document["networks"]),
               "networks_with_non_comment_elements": sum(
                   not n["only_comment_records"] for n in document["networks"]),
               "block_count": sum("block" in n for n in document["elements"]),
               "embedded_st_count": sum("embedded_st" in n for n in document["elements"])}
    result = {k: v for k, v in document.items() if k not in
              ("variables", "elements", "connections", "networks", "unlinked_drawing_sides")}
    result.update(section=section, summary=summary, offset=offset, limit=limit)
    if section == "summary":
        items = document["networks"]
    elif section == "variables":
        require(document["variables"] is not None, "variable table not supplied by standalone LD container")
        items = document["variables"]
    elif section == "network":
        require(1 <= network <= len(document["networks"]), "network marker out of range")
        result["network"] = document["networks"][network - 1]
        items = sorted((n for n in document["elements"]
                        if n["network_marker_ordinal"] == network),
                       key=lambda n: (n["row_raw"], n["column_raw"], n["id"]))
    else:
        raise BridgeError("Unknown ladder inspection section.")
    page = items[offset:offset + limit]
    result.update(items=page, total=len(items),
                  next_offset=offset + limit if offset + limit < len(items) else None)
    if section == "network":
        ids = {n["id"] for n in page}
        # Keep all memberships, including off-page IDs, so pagination cannot
        # silently turn a branched connection into a two-element chain.
        result["connections"] = [c for c in document["connections"] if c["id"] != 0 and
                                 ids.intersection(c["left_elements"] + c["right_elements"])]
        result["left_bus_connection_omitted"] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("--section", choices=("summary", "variables", "network"), default="summary")
    parser.add_argument("--network", type=int, default=1)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        path = args.native.resolve(strict=True)
        require(path.suffix.lower() in (".fb", ".ld"), "this probe accepts only FB or LD files")
        with path.open("rb") as source:
            raw = source.read(MAX_NATIVE_SIZE + 1)
        document = inspect_bytes(raw) if path.suffix.lower() == ".fb" else inspect_program_bytes(raw)
        result = project_result(document, args.section, args.network, args.offset, args.limit)
        result["native"] = str(path)
    except (OSError, BridgeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
