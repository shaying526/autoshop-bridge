"""Read-only project inventory; the HCPP registration is a possibly stale mirror."""

import json
import sys
import struct
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from pathlib import Path, PureWindowsPath

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE, decode
from autoshop_bridge.formats.native import parse
from autoshop_bridge.storage import sha256, utc_now
from autoshop_bridge.formats.structure import parse as parse_structure
from autoshop_bridge.formats.tables import parse as parse_table
from autoshop_bridge.formats.instances import parse as parse_instances


def bounded_read(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_NATIVE_SIZE + 1)
    if len(data) > MAX_NATIVE_SIZE:
        raise BridgeError("Project input exceeds 16 MiB: {}".format(path))
    return data


def member_path(name):
    value = PureWindowsPath(name)
    parts = name.replace("\\", "/").split("/")
    if (
        not name
        or value.is_absolute()
        or value.drive
        or value.root
        or any(p in ("", "..", ".") or p.endswith((".", " ")) for p in parts)
        or any(c in name for c in ':<>"|?*')
        or any(ord(c) < 32 for c in name)
        or any(PureWindowsPath(p).is_reserved() for p in parts)
    ):
        raise BridgeError("Unsafe project member path: {!r}".format(name))
    return value.parts


def _mirror_contents(raw, *, allow_readonly_tail=False):
    if len(raw) > MAX_NATIVE_SIZE:
        raise BridgeError("HCPP input exceeds 16 MiB.")
    if len(raw) < 40 or raw[:4] != b"PPCH":
        raise BridgeError("Unsupported HCPP header.")
    expected = struct.unpack_from("<I", raw, 6)[0]
    compressed_length = struct.unpack_from("<I", raw, 10)[0]
    count = struct.unpack_from("<I", raw, 32)[0]
    # Sample-supported profile, not a complete vendor format specification.
    if raw[4:6] != b"\x00\x03" or raw[14:32] != bytes(18):
        raise BridgeError("Unsupported HCPP header profile.")
    if not 1 <= expected <= MAX_NATIVE_SIZE or not 1 <= count <= 10000:
        raise BridgeError("Unsupported HCPP length/count.")
    if compressed_length != len(raw) - 40:
        raise BridgeError("Invalid HCPP compressed length.")
    compressed = raw[36:-4]
    crc = zlib.crc32(compressed)
    if struct.unpack_from("<I", raw, len(raw) - 4)[0] != crc:
        raise BridgeError("Invalid HCPP compressed CRC32.")
    decoder = zlib.decompressobj()
    try:
        data = decoder.decompress(compressed, expected + 1)
    except zlib.error as exc:
        raise BridgeError("Invalid HCPP compressed data.") from exc
    if (
        not decoder.eof
        or len(data) != expected
        or decoder.unconsumed_tail
        or decoder.unused_data
    ):
        raise BridgeError("Invalid HCPP compressed boundaries.")
    result, names, pos = {}, {}, 0
    for _ in range(count):
        if pos + 8 > len(data):
            raise BridgeError("Truncated HCPP member header.")
        block, size = struct.unpack_from("<II", data, pos)
        if not 1 <= size <= 1024 or pos + 12 + size > len(data):
            raise BridgeError("Invalid HCPP member name boundary.")
        try:
            name = data[pos + 8 : pos + 8 + size].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BridgeError("Invalid HCPP member name encoding.") from exc
        parts = member_path(name)
        length = struct.unpack_from("<I", data, pos + 8 + size)[0]
        if block != 12 + size + length or pos + block > len(data):
            raise BridgeError("Invalid HCPP member data boundary.")
        content = data[pos + 12 + size : pos + block]
        key = "/".join(parts).casefold()
        # The observed archive repeats one hardware file byte-for-byte.
        # Accept identical entries only; never select among different versions.
        if key in names:
            if result[names[key]] != content:
                raise BridgeError("Conflicting duplicate HCPP member name.")
        else:
            names[key] = name
            result[name] = content
        pos += block
    tail = data[pos:]
    # Count + every block length locate this suffix independently of its value.
    # Integrity proves bounded extraction, NOT the suffix's business semantics.
    # Read-only consumers expose it as opaque; mutation callers remain strict.
    if len(tail) != 4 or (not allow_readonly_tail and tail != bytes(4)):
        raise BridgeError(
            "Unsupported HCPP member tail: decompressed_offset={}, "
            "member_count={}, tail_length={}, tail_hex={}, policy={}.".format(
                pos, count, len(tail), tail[:16].hex(),
                "readonly" if allow_readonly_tail else "strict",
            )
        )
    return result, dict(
        profile="ppch-0003-bounded-members-v1",
        validation="bounded_extraction_only",
        archive_sha256=sha256(raw), compressed_crc32="{:08x}".format(crc),
        compressed_crc32_verified=True, decompressed_size=len(data),
        member_count=count, unique_member_count=len(result),
        member_tail_offset=pos, member_tail_hex=tail.hex(),
        member_tail_semantics="unknown", strict_tail_accepted=(tail == bytes(4)),
    )


def unpack_mirror(raw, *, allow_readonly_tail=False):
    return _mirror_contents(raw, allow_readonly_tail=allow_readonly_tail)[0]


def _shared_read(path):
    """Ordinary read handle with maximum sharing; never bypass existing shares."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                               ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        chunks, total = [], 0
        while total <= MAX_NATIVE_SIZE:
            buffer = ctypes.create_string_buffer(min(65536, MAX_NATIVE_SIZE + 1 - total))
            size = wintypes.DWORD()
            if not kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(size), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not size.value:
                return b"".join(chunks)
            chunks.append(buffer.raw[:size.value])
            total += size.value
        raise BridgeError("Project input exceeds 16 MiB: {}".format(path))
    finally:
        kernel.CloseHandle(handle)


def _read_hcp(path):
    try:
        return bounded_read(path)
    except PermissionError:
        if sys.platform != "win32":
            raise
        return _shared_read(path)


def registration(raw):
    decoded = decode(raw)
    if not decoded.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise BridgeError("Unsupported HCP encoding.")
    try:
        text = decoded.decode("utf-16")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise BridgeError("HCP XML declarations are unsupported.")
        root = ET.fromstring(text)
    except (UnicodeError, ET.ParseError) as exc:
        raise BridgeError("Unsupported HCP XML.") from exc
    if root.tag != "project":
        raise BridgeError("Unsupported HCP root.")
    return root


def select_project(project):
    project = project.resolve(strict=True)
    if project.is_file():
        if project.suffix.lower() != ".hcp":
            raise BridgeError("Specify a .hcp file or a directory with one .hcp.")
        return project
    files = [p for p in project.iterdir() if p.is_file() and p.suffix.lower() == ".hcp"]
    if len(files) != 1:
        raise BridgeError(
            "Expected one .hcp in project directory; specify the exact file."
        )
    return files[0]


def program_language(suffix, file_type, program_type):
    """Identify observed registration languages without parsing ladder bodies."""
    if suffix == ".ld":
        return "LD", "file_extension"
    if suffix == ".st":
        return "ST", "file_extension"
    if (
        suffix == ".fb"
        and (file_type or "").strip() == "45"
        and (program_type or "").strip() == "7"
    ):
        return "LD", "registration_file_type"
    return None, None


def scan(project, *, allow_readonly_tail=False):
    hcp = select_project(project)
    directory = hcp.parent
    source = {"path": str(hcp), "kind": "hcp", "possibly_stale": False}
    try:
        raw = _read_hcp(hcp)
    except PermissionError as exc:
        mirror = hcp.with_suffix(".hcpp")
        winerror = getattr(exc, "winerror", None)
        reason = "sharing_violation" if winerror == 32 else "access_denied"
        try:
            members, validation = _mirror_contents(
                bounded_read(mirror), allow_readonly_tail=allow_readonly_tail
            )
            matches = [v for k, v in members.items() if k.casefold() == hcp.name.casefold()]
            if len(matches) != 1:
                raise BridgeError("HCPP does not contain the selected HCP registration.")
            raw = matches[0]
            root = registration(raw)
        except (OSError, BridgeError) as mirror_exc:
            raise BridgeError(
                "HCP registration unavailable: {} ({}; {}; winerror={}); "
                "HCPP fallback failed: {}: {} "
                "In AutoShop, review disk/editor differences and save only changes "
                "you intend to keep, then close the entire target project and retry. "
                "Closing document tabs is insufficient; exiting AutoShop is unnecessary.".format(
                    hcp.name, type(exc).__name__, reason, winerror, mirror.name, mirror_exc
                )
            ) from mirror_exc
        source = {
            "path": str(mirror),
            "member": hcp.name,
            "kind": "hcpp_mirror",
            "possibly_stale": True,
            "hcp_read_error": str(exc),
            "hcp_read_reason": reason,
            "hcp_winerror": winerror,
            "mirror_validation": validation,
        }
    else:
        root = registration(raw)
    source["sha256"] = sha256(raw)
    files, seen = [], set()
    for node in root.findall("file"):
        name = node.findtext("FileName") or ""
        row = {
            "id": node.get("id"),
            "name": node.findtext("Caption"),
            "file": name,
            "file_type_raw": node.findtext("FileType"),
            "program_type_raw": node.findtext("ProgType"),
        }
        if not name:
            row.update(status="unresolved", reason="empty_registration_filename")
            files.append(row)
            continue
        parts = member_path(name)
        path = directory.joinpath(*parts).resolve()
        if directory not in path.parents:
            raise BridgeError(
                "Registered file resolves outside project: {}".format(name)
            )
        if str(path).casefold() in seen:
            raise BridgeError("Duplicate project file registration: {}".format(name))
        seen.add(str(path).casefold())
        row["path"] = str(path)
        suffix = path.suffix.lower()
        row["kind"] = {
            ".st": "st_program",
            ".fb": "function_block",
            ".fc": "function_pending",
            ".gvt": "global_variables",
            ".svt": "system_variables",
            ".stru": "structure",
            ".ld": "ladder_pending",
            ".fbi": "function_block_instances",
            ".fci": "function_instances_pending",
        }.get(suffix, "configuration_pending")
        if suffix == ".svt":
            row.update(read_only=True, reason="external_system_definitions_required")
        if suffix in (".st", ".fb", ".fc", ".ld"):
            row["language"], row["language_evidence"] = program_language(
                suffix, row["file_type_raw"], row["program_type_raw"]
            )
            if row["language"] == "LD":
                row["reason"] = "ladder_not_supported"
        try:
            data = bounded_read(path)
            row.update(
                size=len(data), sha256=sha256(data), status="identified_not_parsed"
            )
            if row.get("language") == "LD":
                pass  # Identity/hash only; no ladder content or variable parsing.
            elif suffix in (".st", ".fb", ".fc"):
                obj = parse(data, suffix[1:])
                row.update(
                    status="parsed",
                    source_bytes=len(obj.source),
                    source_sha256=sha256(obj.source),
                    line_count=obj.line_count,
                )
                row.update(
                    line_table_count=obj.line_table_count,
                    line_metadata_matches_source=(obj.line_metadata_matches_source
                                                  if suffix == ".fc" else obj.line_table_count == obj.line_count),
                )
                if suffix in (".fb", ".fc"):
                    row.update(language="ST", language_evidence="native_st_body")
                    if suffix == ".fc":
                        row["kind"] = "function"
                    row["variables"] = obj.variable_document()
                    row["variable_count"] = len(obj.variables)
                    row["type_dependencies"] = sorted(
                        set(v.type_text for v in obj.variables if v.type_text)
                    )
            elif suffix == ".stru":
                row["structure"] = parse_structure(data)
                row.update(
                    status="parsed", member_count=len(row["structure"]["members"])
                )
            elif suffix == ".gvt":
                obj = parse_table(data, "gvt")
                row.update(
                    status="parsed", variable_count=len(obj.rows), table=obj.document()
                )
            elif suffix == ".fbi":
                obj = parse_instances(data)
                row.update(
                    status="parsed",
                    instances=obj,
                    instance_count=obj["instance_count"],
                    type_dependencies=sorted(
                        {r["data_type"] for r in obj["instances"]}
                    ),
                )
        except (OSError, BridgeError) as exc:
            row.update(status="unreadable_or_unsupported", error=str(exc))
        files.append(row)
    registered = {str(Path(f["path"])).casefold() for f in files if "path" in f}
    extra = [
        {"file": p.name, "kind": "unregistered_file", "status": "not_parsed"}
        for p in sorted(directory.iterdir())
        if p.is_file()
        and str(p.resolve()).casefold() not in registered
        and p.suffix.lower() in (".st", ".fb", ".fc", ".gvt", ".stru", ".fbi", ".fci", ".svt")
    ]
    return {
        "status": "scanned",
        "schema": 1,
        "read_only": True,
        "project": str(directory),
        "project_file": str(hcp),
        "scanned_at": utc_now(),
        "registration_source": source,
        "project_metadata": {
            k: root.findtext(k) for k in ("ProjectDesc", "GCMModal", "ProjVersion")
        },
        "counts": dict(Counter(f.get("kind", "unresolved") for f in files)),
        "files": files,
        "unregistered_files": extra,
        "limitations": [
            "Disk snapshot; unsaved editor changes are not included.",
            "HCPP registration may be stale; bodies and variables use current native files.",
            "Unsupported table layouts are reported individually; unknown metadata and type codes remain raw.",
            "FC, hardware, serial, EtherCAT and axis configuration are pending.",
            "LD programs and observed LD function blocks are identified only; ladder parsing/editing is not implemented.",
        ],
    }


def summary(project, limit=20, offset=0):
    """AI-first inventory page without bodies, initializer text or table rows."""
    if (
        type(limit) is not int
        or not 1 <= limit <= 100
        or type(offset) is not int
        or not 0 <= offset <= 100000
    ):
        raise BridgeError("Summary limit must be 1..100 and offset 0..100000.")
    inventory = scan(project, allow_readonly_tail=True)
    objects, pending = [], Counter()
    programming = {
        "st_program",
        "function_block",
        "structure",
        "global_variables",
        "system_variables",
        "function_block_instances",
        "function_instances_pending",
        "function_pending",
        "function",
        "ladder_pending",
    }
    fields = (
        "name",
        "file",
        "kind",
        "status",
        "language",
        "language_evidence",
        "reason",
        "read_only",
        "sha256",
        "line_count",
        "line_table_count",
        "line_metadata_matches_source",
        "variable_count",
        "member_count",
        "instance_count",
    )
    for row in inventory["files"]:
        if row.get("kind") not in programming:
            pending[row.get("kind", "unresolved")] += 1
            continue
        brief = {key: row[key] for key in fields if key in row}
        if row.get("error"):
            brief["error"] = row["error"][:512]
        objects.append(brief)
    stamp = [(r.get("file"), r.get("sha256")) for r in inventory["files"]]
    digest = sha256(
        json.dumps(
            dict(registration=inventory["registration_source"]["sha256"], files=stamp),
            sort_keys=True,
        ).encode("utf-8")
    )
    return dict(
        status="project_summary",
        schema=1,
        read_only=True,
        source="disk",
        project=inventory["project"],
        registration_source=inventory["registration_source"],
        snapshot_sha256=digest,
        counts=inventory["counts"],
        pending_counts=dict(pending),
        total_objects=len(objects),
        parsed_objects=sum(r["status"] == "parsed" for r in objects),
        total_global_fb_instances=sum(r.get("instance_count", 0) for r in objects),
        limit=limit,
        offset=offset,
        objects=objects[offset : offset + limit],
        next_offset=offset + limit if offset + limit < len(objects) else None,
        unregistered_count=len(inventory["unregistered_files"]),
        limitations=inventory["limitations"],
    )
