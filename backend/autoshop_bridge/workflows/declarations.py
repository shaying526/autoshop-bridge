"""Small read-only declaration snapshots; hashes identify records, not authority."""

import json
import os
import stat
from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import declaration_delete, fb, fc, tables, instances
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
from autoshop_bridge.storage import sha256, write_json_new


def _bounded_regular_read(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise BridgeError("Declaration inputs cannot traverse symbolic links or reparse points.")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise BridgeError("Declaration input must be a regular file with one hard link.")
    if info.st_size > MAX_NATIVE_SIZE:
        raise BridgeError("Declaration input exceeds 16 MiB.")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1):
            raise BridgeError("Declaration input changed before reading.")
        raw = stream.read(MAX_NATIVE_SIZE + 1)
        after = os.fstat(stream.fileno())
    if (len(raw) > MAX_NATIVE_SIZE or len(raw) != opened.st_size
            or (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
            or after.st_nlink != 1):
        raise BridgeError("Declaration input changed or exceeded its read limit.")
    return path, raw


def read(native, output=None):
    """Read supported FB/FC/STRU/GVT/FBI definitions without returning ST source.

    No Windows/AutoShop connection, reference approval or write authority is
    implied. Optional JSON output is created exclusively and never overwritten.
    """
    kind = Path(native).suffix.lower().lstrip(".")
    if kind not in ("fb", "fc", "stru", "gvt", "fbi"):
        raise BridgeError("Declarations read supports only .FB/.FC/.STRU/.GVT/.FBI files.")
    path, raw = _bounded_regular_read(native)
    baselines = declaration_delete.record_baselines(raw, kind)
    if kind in ("fb", "fc"):
        obj = (fb if kind == "fb" else fc).parse(raw)
        definitions = [row.as_dict(i) for i, row in enumerate(obj.variables)]
    elif kind == "fbi":
        definitions = instances.parse(raw)["instances"]
    else:
        definitions = [row.document() for row in tables.parse(raw, kind).rows]
    fields = ("name", "category", "category_code", "data_type", "type_code",
              "type_text_raw", "comment", "initial_value_raw")
    rows = [dict({key: definition[key] for key in fields if key in definition},
                 record_sha256=baseline["record_sha256"])
            for definition, baseline in zip(definitions, baselines)]
    result = dict(status="read", read_only=True, native=str(path),
                  native_sha256=sha256(raw), kind=kind, declcount=len(rows),
                  declarations=rows, authorizes_write=False)
    if output is not None:
        write_json_new(Path(output), result)
    return result


def read_changes(path):
    """Load a bounded explicit operation document before any UI connection."""
    _, raw = _bounded_regular_read(path)
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise BridgeError("Invalid declaration changes JSON.") from exc
    if (not isinstance(document, dict) or set(document) != {"schema", "operations"}
            or type(document["schema"]) is not int or document["schema"] != 1
            or not isinstance(document["operations"], list)
            or not 1 <= len(document["operations"]) <= 32):
        raise BridgeError("Declaration changes require schema=1 and 1..32 operations.")
    for op in document["operations"]:
        if (not isinstance(op, dict)
                or set(op) != {"op", "name", "expected_record_sha256"}
                or op["op"] != "delete" or not isinstance(op["name"], str)
                or not op["name"]):
            raise BridgeError("Declaration delete requires op/name/expected_record_sha256 only.")
        validate_hash(op["expected_record_sha256"])
    return document


def validate_hash(value):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise BridgeError("Expected a lowercase SHA-256 of exactly 64 hexadecimal characters.")
