"""Registered, parsed named-type dependencies for explicit IDE additions."""

from pathlib import Path
import re
from autoshop_bridge.errors import BridgeError
from autoshop_bridge.projects.inventory import scan
from autoshop_bridge.storage import assert_hash

SCALARS = {"BOOL": 1, "INT": 4, "DINT": 16}


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

    def visit(name):
        if name in SCALARS:
            return
        key = name.casefold()
        if key in active or (owner and key == owner.casefold()):
            raise BridgeError(
                "Recursive FB/structure containment is unsupported: " + name
            )
        row = definitions.get(key)
        if not row or Path(row["path"]).stem != name or row.get("status") != "parsed":
            raise BridgeError(
                "Named type must be an exact registered, parsed project FB/structure: "
                + str(name)
            )
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
                visit(dtype)
            elif (
                code == 2048
                and isinstance(dtype, str)
                and re.fullmatch(r"STRING<[1-9][0-9]{0,3}>", dtype)
            ):
                pass  # Existing bounded string member, initialized by the IDE.
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
