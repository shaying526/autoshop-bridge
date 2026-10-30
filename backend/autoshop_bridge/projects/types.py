"""Registered, parsed named-type dependencies for explicit IDE additions."""

from pathlib import Path
from autoshop_bridge.errors import BridgeError
from autoshop_bridge.projects.inventory import scan
from autoshop_bridge.storage import assert_hash
from autoshop_bridge.formats.scalar_types import descriptor

SCALARS = {"BOOL": 1, "INT": 4, "DINT": 16, "REAL": 32}


def selector_name(name):
    scalar=descriptor(name)
    return 'STRING' if scalar is not None and scalar.string_length is not None else name


def catalog(project, requested, owner=None):
    inventory = scan(project)
    definitions = {}
    for row in inventory["files"]:
        if row.get("kind") in ("function_block", "structure"):
            name = Path(row["path"]).stem
            if name.casefold() in definitions:
                raise BridgeError("Ambiguous registered type name.")
            definitions[name.casefold()] = row
    types, hashes, active = {}, {}, set()

    def visit(name, native_fb_reference=False):
        if descriptor(name) is not None:
            return
        key = name.casefold()
        if key in active or (owner and key == owner.casefold()):
            raise BridgeError(
                "Recursive FB/structure containment is unsupported: " + name
            )
        row = definitions.get(key)
        canonical = Path(row["path"]).stem if row else None
        if (not row or row.get("status") != "parsed"
                or (canonical != name and not (native_fb_reference
                    and row["kind"] == "function_block" and canonical.upper() == name))):
            raise BridgeError(
                "Named type must be an exact registered, parsed project FB/structure: "
                + str(name)
            )
        name = canonical
        if name in types:
            return
        active.add(key)
        if row["kind"] == "structure":
            members = row["structure"]["members"]
        else:
            members = row["variables"]["variables"]
        for member in members:
            code, dtype = member["type_code"], member["data_type"]
            if code in (64, 256):
                if not dtype:
                    raise BridgeError("Unresolved dependent type.")
                visit(dtype, native_fb_reference=code == 256)
            elif code == 2048:
                scalar = descriptor(dtype)
                if scalar is None or scalar.code != code or scalar.canonical != dtype:
                    raise BridgeError("Unsupported dependent type layout: " + str(dtype))
                # Capacity belongs to the native STRING descriptor. Its
                # recognition does not qualify a new initializer profile or
                # assert that this capacity is supported by the target PLC.
            elif code not in (1, 4, 16, 32):
                raise BridgeError("Unsupported dependent type layout: " + str(dtype))
        active.remove(key)
        types[name] = dict(
            code=64 if row["kind"] == "structure" else 256, path=row["path"]
        )
        hashes[row["path"]] = row["sha256"]

    for name in requested:
        visit(name)
    return dict(types=types, hashes=hashes)


def check(context):
    for path, expected in context["hashes"].items():
        assert_hash(Path(path), expected)


def ide_catalog(project, requested, owner=None, *, target=None, fb_only=False):
    """Qualify named types whose default records will be produced by the IDE.

    Project definitions are identified, not recursively interpreted. Freeze all
    available definition bytes, including unknown/LD bodies, so a dependency
    cannot change while AutoShop initializes the requested instance. Qualified
    library names have no project definition; they remain provisional until the
    real IDE selector confirms one exact choice. This is not a file encoder or
    a catalog of all types installed in AutoShop.
    """
    inventory = scan(project)
    definitions, hashes = {}, {}
    target_path = str(Path(target).resolve()).casefold() if target is not None else None
    for row in inventory["files"]:
        if row.get("kind") not in ("function_block", "structure"):
            continue
        name = Path(row["path"]).stem
        definitions.setdefault(name.casefold(), []).append(row)
        if row.get("sha256") and str(Path(row["path"]).resolve()).casefold() != target_path:
            hashes[row["path"]] = row["sha256"]
    types = {}
    for name in requested:
        if not isinstance(name, str) or not name:
            raise BridgeError("Expected an exact named IDE type.")
        try:
            size = len(name.encode("utf-8"))
        except UnicodeError as exc:
            raise BridgeError("Invalid Unicode in named IDE type.") from exc
        if size > 512:
            raise BridgeError("Expected an exact named IDE type.")
        if descriptor(name) is not None:
            continue
        matches = definitions.get(name.casefold(), [])
        if len(matches) > 1:
            raise BridgeError("Ambiguous registered type name: " + name)
        if matches:
            row = matches[0]
            if Path(row["path"]).stem != name:
                raise BridgeError("Named IDE type must match the exact registered spelling: " + name)
            if row.get("status") != "parsed" and not (
                row["kind"] == "function_block"
                and row.get("language") == "LD"
                and row.get("status") == "identified_not_parsed"
            ):
                raise BridgeError("Registered IDE type identity/layout is not identified: " + name)
            if not row.get("sha256"):
                raise BridgeError("Registered IDE type has no readable baseline: " + name)
            types[name] = dict(code=64 if row["kind"] == "structure" else 256,
                               path=row["path"], source="registered_project")
        elif len(name.split(".")) > 1 and all(part.isidentifier() for part in name.split(".")):
            types[name] = dict(code=256 if fb_only else "ide_resolved", source="qualified_ide_selector")
        else:
            raise BridgeError(
                "Unregistered single-part IDE types are not implemented; "
                "use an exact registered type or a qualified library FB name: " + name
            )
    return dict(types=types, hashes=hashes)
