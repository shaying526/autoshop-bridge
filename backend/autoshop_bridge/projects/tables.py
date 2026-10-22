"""Conservative sibling-GVT namespace snapshots for new global declarations.

Only the target is written. Other GVT files are checked and cooperatively locked;
this is not a multi-file transaction and cannot lock AutoShop's unsaved buffers.
"""

from contextlib import contextmanager, ExitStack
from pathlib import Path

from autoshop_bridge.errors import BridgeError, ConflictError
from autoshop_bridge.storage import native_file, sha256, target_lock
from autoshop_bridge.formats.tables import parse


def global_files(directory):
    files = sorted(
        (p for p in directory.iterdir() if p.suffix.lower() == ".gvt"),
        key=lambda p: p.name.casefold(),
    )
    if (
        not files
        or len(files) > 256
        or len({p.name.casefold() for p in files}) != len(files)
    ):
        raise BridgeError("Unsupported global table directory.")
    return [native_file(p) for p in files]


def capture(target):
    tables = {}
    for path in global_files(target.parent):
        raw = path.read_bytes()
        parse(raw, "gvt")  # Unknown sibling layouts cannot be ignored for new names.
        tables[path.name] = sha256(raw)
    return dict(schema=1, directory=str(target.parent), tables=tables)


def enabled(manifest, operations):
    return manifest["kind"] == "gvt" and any(op["op"] == "add" for op in operations)


def validate(manifest, operations, target, include_target=True):
    if not enabled(manifest, operations):
        return
    target = native_file(target)
    original = native_file(Path(manifest["native_path"]))
    context = manifest.get("global_context")
    if (
        target != original
        or not isinstance(context, dict)
        or context.get("schema") != 1
        or context.get("directory") != str(target.parent)
        or not isinstance(context.get("tables"), dict)
        or context["tables"].get(target.name) != manifest["native_sha256"]
    ):
        raise BridgeError(
            "Global additions require a fresh export with its original global-table context."
        )
    files = global_files(target.parent)
    if {p.name for p in files} != set(context["tables"]):
        raise ConflictError(
            "Global table set changed; export again before adding variables."
        )
    other_names = set()
    for path in files:
        if path == target and not include_target:
            continue
        raw = path.read_bytes()
        if sha256(raw) != context["tables"][path.name]:
            raise ConflictError("Global table context changed: {}.".format(path.name))
        if path != target:
            other_names.update(r.name.casefold() for r in parse(raw, "gvt").rows)
    for op in operations:
        if op["op"] == "add" and op["name"].casefold() in other_names:
            raise BridgeError(
                "Global variable already exists in another table: {}.".format(
                    op["name"]
                )
            )


@contextmanager
def lock_others(manifest, operations, target):
    if not enabled(manifest, operations):
        yield
        return
    validate(manifest, operations, target)
    with ExitStack() as stack:
        for path in global_files(target.parent):
            if path != target:
                stack.enter_context(target_lock(path))
        validate(manifest, operations, target)
        yield
