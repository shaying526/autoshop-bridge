"""Closed-project structure renames with explicit dependent metadata and receipts."""
from pathlib import Path
import uuid

from autoshop_bridge.errors import BridgeError, ConflictError
from autoshop_bridge.formats import fb, tables, instances
from autoshop_bridge.formats import structure_rename as native
from autoshop_bridge.projects import inventory
from autoshop_bridge.storage import read_json, regular_file, sha256, write_json_new, write_new
from autoshop_bridge.workflows import offline

PROFILE = "structure-member-rename-v1"


def candidates(manifest, blobs, changes):
    if (not isinstance(changes, dict) or set(changes) != {"schema", "structures"}
            or changes["schema"] != 1 or not isinstance(changes["structures"], list)
            or not 1 <= len(changes["structures"]) <= 100):
        raise BridgeError("Rename request requires schema=1 and 1..100 structures.")
    output, definitions, renamed, metadata, skipped = {}, {}, [], [], []
    for entry in changes["structures"]:
        if not isinstance(entry, dict) or set(entry) != {"file", "renames"} or not isinstance(entry["file"], str):
            raise BridgeError("Structure rename requires exact file/renames fields.")
        name = "/".join(inventory.member_path(entry["file"]))
        if (name not in manifest["registered"] or name not in blobs
                or Path(name).suffix.lower() != ".stru" or name in output):
            raise BridgeError("Rename target must be one exact registered structure.")
        result, definition, mapping = native.structure(blobs[name], entry["renames"])
        if definition.name in definitions:
            raise BridgeError("Ambiguous structure type identity.")
        definitions[definition.name] = (definition, mapping)
        output[name] = result
        renamed.extend(dict(file=name, structure=definition.name, old=k, new=v) for k,v in mapping.items())
    affected_fb = set()
    # Parse identified ST FBs independently; unrelated LD/configuration is only
    # hash-protected. Failure to analyze business references does not block edits.
    for name, row in manifest["registered"].items():
        if name not in blobs or Path(name).suffix.lower() != ".fb":
            continue
        if inventory.program_language(".fb", row.get("file_type_raw"), row.get("program_type_raw"))[0] == "LD":
            skipped.append(dict(file=name, reason="ladder_body_not_rewritten"))
            continue
        try:
            obj = fb.parse(blobs[name])
        except BridgeError:
            skipped.append(dict(file=name, reason="unparsed_fb_not_rewritten"))
            continue
        if any(v.type_code == 64 and v.type_text in definitions for v in obj.variables):
            affected_fb.add(obj.program_name)
            result, updates = native.fb_initializers(blobs[name], definitions)
            if result != blobs[name]:
                output[name] = result
            metadata.extend(dict(file=name, **u) for u in updates)
    for name, row in manifest["registered"].items():
        if name not in blobs or Path(name).suffix.lower() not in (".gvt", ".fbi"):
            continue
        if Path(name).suffix.lower() == ".gvt":
            try:
                obj = tables.parse(blobs[name], "gvt")
            except BridgeError:
                skipped.append(dict(file=name, reason="unparsed_global_table_not_rewritten"))
                continue
            replacements = []
            for var in obj.rows:
                if var.type_code == 64 and var.type_text in definitions:
                    definition, mapping = definitions[var.type_text]
                    value = native.initializer(var.initial_raw, definition, mapping)
                    if value != var.initial_raw:
                        start, end = var.spans["initial_value"]
                        replacements.append((start, end, tables.string(value)))
                        metadata.append(dict(file=name, variable=var.name, structure=var.type_text, field="initial_value_raw"))
            if replacements:
                output[name] = native.replace_spans(blobs[name], replacements)
                tables.parse(output[name], "gvt")
        else:
            try:
                obj = instances.parse(blobs[name])
            except BridgeError:
                skipped.append(dict(file=name, reason="unparsed_instance_table_not_rewritten"))
                continue
            for var in obj["instances"]:
                if var["data_type"] in affected_fb and var["initial_value_raw"]:
                    raise BridgeError("Associated FB instance has a nonempty nested initializer requiring its own observed rename profile: " + name)
    output = {name: data for name,data in output.items() if data != blobs[name]}
    return output, dict(renamed_members=renamed, metadata_updates=metadata,
                       references_updated=False, reference_check="not_performed_by_design",
                       unchanged_unparsed_objects=skipped, compile_pending=True)


def plan(project, changes_file, workspace):
    offline._no_links(changes_file)
    changes = read_json(regular_file(Path(changes_file)))
    offline.export(project, workspace)
    workspace, manifest = offline._load(workspace)
    blobs = offline._assert_baseline(manifest)
    result, details = candidates(manifest, blobs, changes)
    targets = []
    for index, (name, raw) in enumerate(result.items()):
        path = workspace / ("rename-candidate-{}.native".format(index))
        write_new(path, raw)
        targets.append(dict(file=name, candidate=path.name, sha256=sha256(raw)))
    offline._assert_baseline(manifest)
    document = dict(schema=1, profile=PROFILE, workspace=str(workspace),
                    manifest_sha256=offline._digest(manifest), changes=changes, targets=targets, details=details)
    path = workspace / "rename-plan.json"
    write_json_new(path, offline._seal(document))
    return dict(status="structure_rename_planned", plan=str(path), plan_sha256=sha256(path.read_bytes()),
                protected_files=len(manifest["hashes"]), targets=targets, **details)


def apply(plan_file, expected_plan_sha256, backup_root, *, guard_factory=None):
    offline._no_links(plan_file)
    plan_file = regular_file(Path(plan_file))
    if sha256(plan_file.read_bytes()) != expected_plan_sha256:
        raise ConflictError("Structure rename plan differs from the explicit digest.")
    document = read_json(plan_file)
    offline._verify(document)
    if document.get("schema") != 1 or document.get("profile") != PROFILE:
        raise BridgeError("Unsupported structure rename plan.")
    workspace, manifest = offline._load(document["workspace"])
    if offline._digest(manifest) != document.get("manifest_sha256"):
        raise ConflictError("Structure rename workspace differs from the plan.")
    blobs = {name: inventory.bounded_read(offline._member(workspace, path)) for name,path in manifest["originals"].items()}
    if any(sha256(raw) != manifest["hashes"][name] for name,raw in blobs.items()):
        raise ConflictError("Structure rename original snapshot changed.")
    regenerated, details = candidates(manifest, blobs, document["changes"])
    expected_targets = [dict(file=name, candidate="rename-candidate-{}.native".format(index), sha256=sha256(raw))
                        for index,(name,raw) in enumerate(regenerated.items())]
    if document.get("targets") != expected_targets or document.get("details") != details:
        raise ConflictError("Rename plan does not equal the complete regenerated request.")
    for row in expected_targets:
        if inventory.bounded_read(offline._member(workspace, row["candidate"])) != regenerated[row["file"]]:
            raise ConflictError("Structure rename candidate changed.")
    result = offline._execute(manifest, regenerated, backup_root,
        guard_factory=guard_factory or offline.exclusive_hcp, reason="structure_member_rename")
    result.update(details)
    return result


def apply_table(target, expected, operations, backup_root):
    """Existing table-apply uses the same complete project rename workflow."""
    target = regular_file(Path(target))
    if sha256(target.read_bytes()) != expected:
        raise ConflictError("Structure table changed since export.")
    if not all(op.get("op") == "set" and op.get("field") == "name" and op.get("expected") == op.get("name")
               for op in operations):
        raise BridgeError("Use a separate name-only changes.json for table-apply rename; other table edits remain available separately.")
    project = None
    for parent in target.parents:
        hcps = [p for p in parent.iterdir() if p.is_file() and p.suffix.lower() == ".hcp"]
        if hcps:
            if len(hcps) != 1:
                raise BridgeError("Multiple project registrations; use structure-rename-plan with an explicit project file.")
            project = parent
            break
    if project is None:
        raise BridgeError("Member rename requires project registration; use structure-rename-plan with the exact project.")
    base = Path(backup_root) if backup_root else project.parent / "autoshop_bridge_artifacts"
    base = offline._outside(base, project)
    workspace = base / ("structure-rename-" + uuid.uuid4().hex)
    base.mkdir(parents=True, exist_ok=True)
    request = base / ("structure-renames-" + uuid.uuid4().hex + ".json")
    write_json_new(request, dict(schema=1, structures=[dict(file=target.relative_to(project).as_posix(),
        renames=[dict(old=op["name"], new=op["value"]) for op in operations])]))
    built = plan(project, request, workspace)
    return apply(Path(built["plan"]), built["plan_sha256"], base)
