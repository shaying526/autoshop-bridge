"""Bounded, explicit-source system definition queries. All sources are read-only."""

from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.system_variables import parse
from autoshop_bridge.projects.inventory import scan, bounded_read
from autoshop_bridge.storage import regular_file, sha256, assert_hash, write_json_new


def read(project, definitions_dir, table=None, type_name=None, search=None,
         limit=20, offset=0, output=None):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 100000:
        raise BridgeError("System query limit must be 1..100 and offset 0..100000.")
    for name in (table, type_name):
        if name is not None and (not isinstance(name, str) or not name.isidentifier()):
            raise BridgeError("System table/type requires an exact identifier.")
    if table is not None and type_name is not None:
        raise BridgeError("Choose a system table or a type, not both.")
    if search is not None and (not isinstance(search, str) or not 1 <= len(search) <= 256):
        raise BridgeError("System search must contain 1..256 characters.")
    directory = Path(definitions_dir).resolve(strict=True)
    if not directory.is_dir():
        raise BridgeError("System definitions directory is required.")
    paths = [regular_file(directory / name) for name in ("SysVarDef.xml", "SysDataTypeDef.xml")]
    data = [bounded_read(path) for path in paths]
    inventory = scan(Path(project), allow_readonly_tail=True)
    model = inventory["project_metadata"].get("GCMModal")
    catalog = parse(*data, model)
    registered = [r for r in inventory["files"] if r.get("kind") == "system_variables"]
    if not registered:
        raise BridgeError("No registered system variable tables in project.")
    if any(not row.get("sha256") for row in registered):
        raise BridgeError("Registered system table cannot be read.")
    definition = None
    if type_name is not None:
        if type_name not in catalog["types"]:
            raise BridgeError("System type was not defined: " + type_name)
        found = catalog["types"][type_name]
        definition = {k: v for k, v in found.items() if k != "members"}
        scope, items = "type_members", list(found["members"])
    else:
        if table is not None and table not in {r["name"] for r in registered}:
            raise BridgeError("System table is not registered: " + table)
        scope, items = ("variables" if table or search else "tables"), []
        for row in registered:
            if table is not None and row["name"] != table:
                continue
            if not row.get("sha256"):
                raise BridgeError("Registered system table cannot be read.")
            found = catalog["tables"].get(row["name"])
            if found is None:
                raise BridgeError("Registered system table has no XML definition: " + row["name"])
            common = dict(table=row["name"], file=row["file"], base_address_raw=found["base_address_raw"])
            if scope == "tables":
                items.append(dict(common, variable_count=len(found["variables"]),
                                  excluded_count=found["excluded_count"], read_only=True))
            else:
                items.extend(dict(variable, **common) for variable in found["variables"])
    if search is not None:
        key = search.casefold()
        items = [r for r in items if key in (r.get("name") or r.get("table") or "").casefold()
                 or key in (r.get("comment") or "").casefold()]
    sources = [dict(path=str(path), sha256=sha256(raw)) for path, raw in zip(paths, data)]
    for source in sources:
        assert_hash(Path(source["path"]), source["sha256"])
    for row in registered:
        if row.get("sha256"):
            assert_hash(Path(row["path"]), row["sha256"])
    result = dict(status="system_variables_read", schema=1, read_only=True, source="vendor_xml",
                  project=inventory["project"], model=model, module_name=catalog["module_name"],
                  registration_source=inventory["registration_source"], definitions=sources,
                  table_sources=[dict(table=r["name"], file=r["file"], sha256=r.get("sha256")) for r in registered],
                  scope=scope, table=table, type_name=type_name, search=search, definition=definition,
                  total_matches=len(items), limit=limit, offset=offset, items=items[offset:offset + limit],
                  next_offset=offset + limit if offset + limit < len(items) else None,
                  model_filter_scope="observed_UnEnableModel_applicability_list",
                  limitations=["Vendor definitions, not runtime PLC values or native SVT declarations.",
                               "Array elements and recursive structures are not expanded; query type_name for direct members.",
                               "Addresses/offsets/bit fields are raw XML; implicit layout and address units are not inferred.",
                               "Unknown types and metadata remain raw; model behavior beyond the observed applicability list is unverified.",
                               "IDE-generated legacy aliases may appear separately in the view; query their containing type for XML members."])
    if output is not None:
        write_json_new(Path(output), result)
        result["output"] = str(Path(output).resolve())
    return result
