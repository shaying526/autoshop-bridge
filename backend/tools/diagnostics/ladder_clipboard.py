"""Observed LD Clip Format V3 records; pure decoder, no Windows/disk access.

GlobalSize is allocation capacity, not serialized length. Only the count-framed
record prefix is exposed; unowned capacity bytes must never be exported as
source. This is not validation of an arbitrary opaque clipboard format.
"""

import bisect
import hashlib
import struct

from autoshop_bridge.formats.fb import Reader
from tools.diagnostics.inspect_autoshop_ladder import element_record, require, u16, MAX_RECORDS

FORMAT = "LD Clip Format V3"
MAX_ALLOCATION = 16 * 1024 * 1024
_UNCONFIGURED_READONLY_PROFILE = "experimental-ld-clipboard-v3-unconfigured-call-readonly-v1"


def decode(raw, *, whole_requested=False):
    return _decode_records(raw, whole_requested=whole_requested)


def _decode_records(raw, *, whole_requested=False, _readonly_unconfigured=False):
    """Shared framing; only the separate readonly entry enables the exception."""
    require(18 <= len(raw) <= MAX_ALLOCATION, "clipboard allocation size")
    reader = Reader(raw, 0, len(raw))
    top, bottom, left, right = struct.unpack("<4I", reader.take(16))
    require(top <= bottom <= MAX_RECORDS and left <= right <= MAX_RECORDS,
            "clipboard selection bounds")
    count = u16(reader)
    require(0 < count <= MAX_RECORDS, "clipboard element count")
    nodes, identities = [], set()
    for _ in range(count):
        node = element_record(reader, clipboard=True,
                              _readonly_clipboard_unconfigured=_readonly_unconfigured)
        require(node["id"] not in identities, "duplicate clipboard element identity")
        require(top <= node["row_raw"] <= bottom and left <= node["column_raw"] <= right,
                "clipboard element outside selection")
        identities.add(node["id"])
        nodes.append(node)
    markers = sorted(n["row_raw"] for n in nodes if n["kind_raw"] == 11)
    require(len(markers) == len(set(markers)), "duplicate clipboard network header row")
    if whole_requested:
        require(top == 0 and left == 0 and markers and markers[0] == 0,
                "whole diagram copy must begin at its first network header")
    groups = {}
    for node in nodes:
        node["network_marker_ordinal"] = (bisect.bisect_right(markers, node["row_raw"])
                                         if markers and node["row_raw"] >= markers[0] else None)
        if node["kind_raw"] in (8, 11):
            continue
        for side in ("left", "right"):
            key = node[side + "_connection"]
            group = groups.setdefault(key, dict(id=key, left_elements=[], right_elements=[],
                                                coverage="selected_members_only"))
            group[side + "_elements"].append(node["id"])
    networks = []
    for ordinal, row in enumerate(markers, 1):
        members = [node for node in nodes if node["network_marker_ordinal"] == ordinal]
        networks.append(dict(ordinal=ordinal, row_raw=row,
                             title=next(n["text"] for n in members if n["kind_raw"] == 11),
                             element_ids=[n["id"] for n in members],
                             only_comment_records=all(n["kind_raw"] == 11 for n in members)))
    result = dict(schema=1, status="ladder_editor_records_read_experimental",
                profile="experimental-ld-clipboard-v3-v1", source="live_windows_clipboard",
                source_disk_read=False, clipboard_format=FORMAT,
                scope="whole_grid_selection_requested" if whole_requested else "current_selection",
                record_structure_complete_within_count=True,
                complete_logic_read=False, logic_semantics_verified=False,
                selection=dict(top=top, bottom=bottom, left=left, right=right),
                serialized_prefix_bytes=reader.pos, allocation_bytes=len(raw),
                allocation_tail_bytes_not_interpreted=len(raw) - reader.pos,
                payload_sha256=hashlib.sha256(raw[:reader.pos]).hexdigest(),
                elements=nodes, networks=networks,
                connections=sorted(groups.values(), key=lambda n: n["id"]),
                summary=dict(element_count=count, network_header_count=len(markers),
                             networks_with_non_comment_elements=sum(not n["only_comment_records"] for n in networks),
                             block_count=sum("block" in n for n in nodes),
                             embedded_st_count=sum("embedded_st" in n for n in nodes)),
                limitations=["Only observed record kinds and layouts are accepted.",
                             "Connections derive from shared pin IDs in selected elements; external members are unknown.",
                             "Runtime pin IDs can differ from saved file IDs; compare relationships, not raw IDs.",
                             "No serialized length is exposed; allocation capacity after counted records is not source.",
                             "Whole-grid selection is an observed UI procedure, not a universal coverage guarantee.",
                             "Execution record framing has only file/synthetic validation; real embedded-ST diagram copy is unverified.",
                             "No complete LD semantics, compilation, or PLC validation."])
    if _readonly_unconfigured:
        # Even the private shared parser cannot return the normal edit profile
        # after accepting a placeholder. Public callers use the separate reader.
        result.update(profile=_UNCONFIGURED_READONLY_PROFILE,
                      status="ladder_editor_unconfigured_profile_readonly",
                      read_only=True, editing_eligible=False, complete_live_graph=False)
    return result


def project_result(document, *, network=None, offset=0, limit=20):
    """Bound AI output after complete decoding; preserve off-page memberships."""
    require(0 <= offset and 1 <= limit <= 100, "invalid editor pagination")
    result = {k: v for k, v in document.items() if k not in ("elements", "networks", "connections")}
    result.update(offset=offset, limit=limit)
    if network is None:
        items = document["networks"] if document["networks"] else document["elements"]
        result["section"] = "networks" if document["networks"] else "selected_elements"
    else:
        require(1 <= network <= len(document["networks"]), "editor network ordinal out of range")
        result["network"] = document["networks"][network - 1]
        result["section"] = "network_elements"
        items = sorted((n for n in document["elements"] if n["network_marker_ordinal"] == network),
                       key=lambda n: (n["row_raw"], n["column_raw"], n["id"]))
    page = items[offset:offset + limit]
    result.update(items=page, total=len(items),
                  next_offset=offset + limit if offset + limit < len(items) else None)
    if network is not None or result["section"] == "selected_elements":
        ids = {n["id"] for n in page}
        result["connections"] = [c for c in document["connections"] if c["id"] != 0
                                 and ids.intersection(c["left_elements"] + c["right_elements"])]
        result["left_bus_connection_omitted"] = True
    return result
