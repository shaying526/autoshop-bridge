"""Explicit disk-only project workspace workflow; no public service integration.

Only existing registered targets are eligible. HCPP never establishes write
authority. Every batch retains an exclusive HCP handle and backs up every
baseline file before its first replacement. Multi-file writes are not atomic;
partial progress and retained backups are returned for explicit recovery.
"""

import os
import json
import stat
import xml.etree.ElementTree as ET
import tempfile
import uuid
from pathlib import Path

from autoshop_bridge.errors import BridgeError, ConflictError, FormatRejection
from autoshop_bridge import storage
from autoshop_bridge.formats import fb, fc, st, tables, instances, declaration_delete
from autoshop_bridge.formats.offline_source import (
    ST_FOLD_ROWS_V1, FB_PRESERVE_ROWS_V1, rebuild_fold_row_st, rebuild_preserved_row_fb,
)
from autoshop_bridge.formats.offline_variables import rebuild_fb
from autoshop_bridge.projects import inventory, deletion_preflight
from autoshop_bridge.projects.offline_guard import exclusive_hcp, OfflineProjectUnavailable, error_code
from autoshop_bridge.projects.identifiers import precheck_addition_names, require_new_identifier

NATIVE_SUFFIXES = {".st", ".fb", ".fc", ".ld", ".stru", ".gvt", ".fbi", ".fci", ".svt"}


def _digest(value):
    return storage.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf8"))


def _seal(value):
    return dict(value, integrity_sha256=_digest(value))


def _verify(value):
    payload = {k: v for k, v in value.items() if k != "integrity_sha256"}
    if value.get("integrity_sha256") != _digest(payload):
        raise ConflictError("Offline metadata integrity changed.")


def _no_links(path):
    for candidate in [Path(path).absolute(), *Path(path).absolute().parents]:
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise BridgeError("Reparse-point and linked paths are unsupported.")
        if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            raise BridgeError("Files with multiple hard links are unsupported.")


def _inside(path, root):
    return path == root or root in path.parents


def _outside(path, project):
    _no_links(path)
    path = Path(path).resolve()
    if _inside(path, project):
        raise BridgeError("Workspace and backups must be outside the project.")
    return path


def _member(project, name):
    parts = inventory.member_path(name)
    path = project.joinpath(*parts)
    _no_links(path)
    for parent in [path, *path.parents]:
        if parent == project:
            break
        if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
            raise BridgeError("Linked project paths are unsupported.")
    path = path.resolve(strict=True)
    if not _inside(path, project) or not path.is_file():
        raise BridgeError("Expected an existing project file within the selected project.")
    return path


def _registered(project, hcp_bytes):
    root = inventory.registration(hcp_bytes)
    entries = {}
    for node in root.findall("file"):
        name = node.findtext("FileName") or ""
        if not name:
            continue  # Explicitly captured by _nonfile_registration, never a target.
        try:
            path = project.joinpath(*inventory.member_path(name))
            _no_links(path)
            path = path.resolve()
            if not _inside(path, project):
                raise BridgeError("Registered filename escapes project.")
            if path.exists():
                path = _member(project, name)
                state = "present"
            else:
                if path.suffix.lower() in NATIVE_SUFFIXES | {".hcp", ".hcpp"}:
                    raise BridgeError("Missing registered native/type dependency.")
                state = "missing_config"
        except (OSError, BridgeError) as exc:
            raise BridgeError("Registered file unavailable or unsafe: {!r}: {}".format(name, exc)) from exc
        key = path.relative_to(project).as_posix()
        if any(k.casefold() == key.casefold() for k in entries):
            raise BridgeError("Duplicate registration filename.")
        entries[key] = {"file": key, "name": node.findtext("Caption"),
                        "file_type_raw": node.findtext("FileType"),
                        "program_type_raw": node.findtext("ProgType"), "state": state}
    return entries


def _nonfile_registration(hcp_bytes):
    return [dict(registration_id=node.get("id"), name=node.findtext("Caption"),
                 file_type_raw=node.findtext("FileType"), program_type_raw=node.findtext("ProgType"),
                 reason="no_standalone_filename", registration_xml=ET.tostring(node, encoding="unicode"))
            for node in inventory.registration(hcp_bytes).findall("file") if not node.findtext("FileName")]


def _names(project, hcp_name, registered):
    names = {name for name, row in registered.items() if row["state"] == "present"} | {hcp_name}
    # Also protect unregistered native files; none become write-authorized.
    for path in project.rglob("*"):
        _no_links(path)
        if path.is_file() and path.suffix.lower() in NATIVE_SUFFIXES:
            names.add(_member(project, path.relative_to(project).as_posix()).relative_to(project).as_posix())
    if len({name.casefold() for name in names}) != len(names):
        raise BridgeError("Protected project filenames collide under casefold comparison.")
    return sorted(names)


def _assert_baseline(manifest, expected=None, locked_hcp=None):
    project = Path(manifest["project"])
    hcp_name = manifest["hcp"]
    current_hcp = locked_hcp if locked_hcp is not None else inventory.bounded_read(_member(project, hcp_name))
    registered = _registered(project, current_hcp)
    if registered != manifest["registered"]:
        raise ConflictError("Project registration changed.")
    if (_nonfile_registration(current_hcp) != manifest["excluded_nonfile_registration"]
            or sorted(name for name, row in registered.items() if row["state"] == "missing_config") != manifest["declared_missing"]):
        raise ConflictError("Nonfile registration or missing-config state changed.")
    expected = expected or manifest["hashes"]
    if _names(project, hcp_name, registered) != sorted(expected):
        raise ConflictError("Protected native file set changed.")
    result = {}
    for name, digest in expected.items():
        data = current_hcp if name == hcp_name else inventory.bounded_read(_member(project, name))
        if storage.sha256(data) != digest:
            raise ConflictError("Project baseline changed: {}".format(name))
        result[name] = data
    return result


def export(project, workspace):
    """Freeze direct-HCP registration, all registered files and extra native files."""
    selected = Path(project)
    _no_links(selected)
    if selected.is_symlink():
        raise BridgeError("Linked project selection is unsupported.")
    hcp = inventory.select_project(selected)
    directory = hcp.parent
    workspace = _outside(workspace, directory)
    if workspace.exists():
        raise BridgeError("Export requires a new workspace directory.")
    try:
        # The normal shared-read retry preserves Win32 sharing diagnostics
        # that Python's CRT file open can reduce to generic errno 13. It never
        # reads HCPP and cannot override another handle's sharing restrictions.
        raw = inventory._read_hcp(hcp)
    except PermissionError as exc:
        if getattr(exc, "winerror", None) in (32, 33):
            raise OfflineProjectUnavailable("requires_close_entire_project: HCP is shared/locked; close the entire selected project, not only its document tabs.", winerror=exc.winerror) from exc
        raise
    registered = _registered(directory, raw)
    names = _names(directory, hcp.name, registered)
    blobs = {name: raw if name == hcp.name else inventory.bounded_read(_member(directory, name)) for name in names}
    manifest = dict(schema=1, project=str(directory), hcp=hcp.name,
                    registration_source="direct_hcp", registered=registered,
                    excluded_nonfile_registration=_nonfile_registration(raw),
                    declared_missing=sorted(name for name, row in registered.items() if row["state"] == "missing_config"),
                    hashes={name: storage.sha256(data) for name, data in blobs.items()}, originals={})
    workspace.mkdir(parents=True)
    for index, (name, data) in enumerate(blobs.items()):
        snapshot = "original-{}.native".format(index)
        storage.write_new(workspace / snapshot, data)
        manifest["originals"][name] = snapshot
    _assert_baseline(manifest)
    storage.write_json_new(workspace / "workspace.json", _seal(manifest))
    return dict(status="exported", workspace=str(workspace), manifest=str(workspace / "workspace.json"),
                protected_files=len(blobs), registration_source="direct_hcp",
                excluded_nonfile_registration_count=len(manifest["excluded_nonfile_registration"]),
                declared_missing_count=len(manifest["declared_missing"]))


def _load(workspace):
    _no_links(workspace)
    workspace = Path(workspace).resolve(strict=True)
    manifest = storage.read_json(_member(workspace, "workspace.json"))
    _verify(manifest)
    if manifest.get("schema") != 1 or manifest.get("registration_source") != "direct_hcp":
        raise BridgeError("Expected a direct-HCP offline workspace.")
    _validate_manifest(manifest)
    _outside(workspace, Path(manifest["project"]))
    if not isinstance(manifest.get("originals"), dict) or set(manifest["originals"]) != set(manifest["hashes"]):
        raise BridgeError("Incomplete offline original snapshot set.")
    originals = {}
    for name, filename in manifest["originals"].items():
        if not isinstance(filename, str):
            raise BridgeError("Invalid original snapshot filename.")
        originals[name] = inventory.bounded_read(_member(workspace, filename))
        if storage.sha256(originals[name]) != manifest["hashes"][name]:
            raise ConflictError("Offline original snapshot changed.")
    if _registered(Path(manifest["project"]), originals[manifest["hcp"]]) != manifest["registered"]:
        raise ConflictError("Frozen direct-HCP registration differs from manifest.")
    return workspace, manifest


def _validate_manifest(manifest):
    if (not isinstance(manifest.get("project"), str)
            or not Path(manifest["project"]).is_absolute()
            or not isinstance(manifest.get("hcp"), str)
            or Path(manifest["hcp"]).suffix.lower() != ".hcp"
            or not isinstance(manifest.get("hashes"), dict)
            or not isinstance(manifest.get("registered"), dict)
            or manifest["hcp"] not in manifest["hashes"]
            or not isinstance(manifest.get("declared_missing"), list)
            or not isinstance(manifest.get("excluded_nonfile_registration"), list)):
        raise BridgeError("Invalid offline project manifest.")
    if ({name for name, row in manifest["registered"].items() if row.get("state") == "present"} - set(manifest["hashes"])
            or sorted(name for name, row in manifest["registered"].items() if row.get("state") == "missing_config") != manifest["declared_missing"]
            or any(row.get("state") not in {"present", "missing_config"} for row in manifest["registered"].values())):
        raise BridgeError("Invalid present/missing registration state.")
    for name, digest in manifest["hashes"].items():
        if not isinstance(name, str) or not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise BridgeError("Invalid offline baseline identity/hash.")
        inventory.member_path(name)


def _changes(workspace, changes_file, manifest):
    _no_links(changes_file)
    changes_file = storage.regular_file(Path(changes_file))
    value = storage.read_json(changes_file)
    if set(value) != {"schema", "targets"} or value["schema"] != 1 or not isinstance(value["targets"], list) or not 1 <= len(value["targets"]) <= 100:
        raise BridgeError("Expected schema=1 and 1..100 explicit targets.")
    entries, seen = [], set()
    for entry in value["targets"]:
        if (not isinstance(entry, dict) or not {"file"} <= set(entry)
                or set(entry) - {"file", "source_file", "variable_operations"}
                or not (set(entry) & {"source_file", "variable_operations"})):
            raise BridgeError("Expected file and source_file or variable_operations.")
        if not isinstance(entry["file"], str) or ("source_file" in entry and not isinstance(entry["source_file"], str)):
            raise BridgeError("Target and source filenames must be text.")
        if "variable_operations" in entry and not isinstance(entry["variable_operations"], list):
            raise BridgeError("Variable operations must be an explicit list.")
        name = "/".join(inventory.member_path(entry["file"]))
        if name not in manifest["registered"] or manifest["registered"][name]["state"] != "present" or name.casefold() in seen:
            raise BridgeError("Target must be uniquely registered with exact filename.")
        if Path(name).suffix.lower() not in {".st", ".fb", ".fc", ".stru", ".gvt", ".fbi"}:
            raise BridgeError("Unsupported offline mutation target.")
        seen.add(name.casefold())
        source = None
        if "source_file" in entry:
            source_path = changes_file.parent.joinpath(*inventory.member_path(entry["source_file"]))
            _no_links(source_path)
            source_path = storage.regular_file(source_path)
            if not _inside(source_path, changes_file.parent):
                raise BridgeError("Source file escapes changes directory.")
            source = inventory.bounded_read(source_path)
            st.validate_program_edit(source)
        entries.append((dict(entry, file=name), source))
    return entries


def check(workspace, changes_file, *, candidate_builder=None):
    workspace, manifest = _load(workspace)
    blobs = _assert_baseline(manifest)
    entries = _changes(workspace, changes_file, manifest)
    _qualify(manifest, blobs, entries, candidate_builder)
    _assert_baseline(manifest)
    result = dict(status="checked", targets=[entry["file"] for entry, _ in entries],
                protected_files=len(manifest["hashes"]), candidate_built=False,
                qualification="format_type_source_and_namespace_checked")
    if _has_deletions(entries):
        result["deletion_preflight_scope"] = deletion_preflight.SCOPE
        result["qualification"] = "explicit_declaration_targets_checked_compile_pending"
        result.update(reference_check="not_performed_by_design", compile_pending=True, cascade=False)
    return result


def default_candidate_builder(entry, raw, source, definitions):
    suffix = Path(entry["file"]).suffix.lower()
    operations = entry.get("variable_operations", [])
    if any(isinstance(op, dict) and op.get("op") == "delete" for op in operations):
        result = declaration_delete.rebuild(raw, suffix[1:], operations)
        if suffix == ".fb" and source is not None:
            return rebuild_preserved_row_fb(result, source, profile=FB_PRESERVE_ROWS_V1)
        if source is not None:
            raise BridgeError("Deletion source_file is supported only for FB; FC source changes remain unsupported offline.")
        return result
    if suffix == ".fb":
        result = rebuild_fb(raw, entry["variable_operations"], definitions) if "variable_operations" in entry else raw
        return rebuild_preserved_row_fb(result, source, profile=FB_PRESERVE_ROWS_V1) if source is not None else result
    if suffix == ".st" and "variable_operations" not in entry and source is not None:
        return rebuild_fold_row_st(raw, source, profile=ST_FOLD_ROWS_V1)
    if suffix == ".fc" and source is None and "variable_operations" in entry:
        from autoshop_bridge.formats.offline_fc import rebuild
        return rebuild(raw, entry["variable_operations"])
    if suffix == ".gvt" and source is None and "variable_operations" in entry:
        from autoshop_bridge.formats.offline_globals import rebuild
        return rebuild(raw, entry["variable_operations"], structure_definitions=definitions)
    if suffix == ".stru" and source is None and "variable_operations" in entry:
        try:
            return tables.parse(raw, "stru").rebuild(entry["variable_operations"])
        except UnicodeError as exc:
            raise BridgeError("Invalid Unicode in offline structure declaration.") from exc
    raise BridgeError("No proven default offline builder for this target/operation.")


def _has_deletions(entries):
    return any(isinstance(op, dict) and op.get("op") == "delete"
               for entry, _ in entries for op in entry.get("variable_operations", []))


def _qualify(manifest, blobs, entries, candidate_builder=None):
    deleting = _has_deletions(entries)
    if deleting:
        if candidate_builder is not None:
            raise BridgeError("Declaration deletion requires the exact default candidate builder.")
        for entry, source in entries:
            operations = entry.get("variable_operations", [])
            if any(not isinstance(op, dict) or op.get("op") != "delete" for op in operations):
                raise BridgeError("Mixed delete and add/set batches are unsupported.")
            suffix = Path(entry["file"]).suffix.lower()
            if suffix == ".fc" and (source is not None or not operations):
                raise BridgeError("Offline FC supports variable deletion only, without source_file.")
            if source is not None and suffix != ".st" and not operations:
                raise BridgeError("Deletion batch source repair requires an ST source or a deletion target FB.")
    else:
        for entry, source in entries:
            suffix = Path(entry["file"]).suffix.lower()
            if suffix == ".fbi":
                raise BridgeError("Offline FBI supports declaration deletion only, without source_file.")
            if suffix == ".fc" and (source is not None or not entry.get("variable_operations")):
                raise BridgeError("Offline FC additions require variable_operations without source_file.")
    definitions = {}
    # Only target records determine deletion eligibility; type users and other
    # native languages remain protected bytes for subsequent AutoShop compilation.
    for name in (() if deleting else manifest["registered"]):
        if Path(name).suffix.lower() == ".stru" and manifest["registered"][name]["state"] == "present":
            try:
                definition = tables.parse(blobs[name], "stru")
            except BridgeError:
                continue
            if definition.name in definitions:
                raise BridgeError("Duplicate structure definition identity.")
            definitions[definition.name] = blobs[name]
    changed_structures = {tables.parse(blobs[entry["file"]], "stru").name.casefold()
                          for entry, _ in entries if Path(entry["file"]).suffix.lower() == ".stru"}
    project_names = {row["name"] for row in manifest["registered"].values() if row.get("name")}
    project_names.update(row["name"] for row in manifest["excluded_nonfile_registration"] if row.get("name"))
    project_names.update(Path(name).stem for name in manifest["registered"])
    globals_needed = any(Path(entry["file"]).suffix.lower() == ".gvt" and any(isinstance(op, dict) and op.get("op") == "add" for op in entry.get("variable_operations", [])) for entry, _ in entries)
    global_names = set()
    if globals_needed:
        for name, raw in blobs.items():
            if Path(name).suffix.lower() == ".gvt":
                global_names.update(row.name for row in tables.parse(raw, "gvt").rows)
            elif Path(name).suffix.lower() == ".fbi":
                global_names.update(row["name"] for row in instances.parse(raw)["instances"])
    for entry, _ in entries:
        operations = entry.get("variable_operations", [])
        precheck_addition_names(dict(operations=operations))
        suffix = Path(entry["file"]).suffix.lower()
        local_names = {v.name for v in fb.parse(blobs[entry["file"]]).variables} if suffix == ".fb" and operations else set()
        if suffix == ".fc" and operations:
            local_names = {v.name for v in fc.parse(blobs[entry["file"]]).variables}
        for op in operations:
            if not isinstance(op, dict):
                raise BridgeError("Each variable operation must be an object.")
            if op.get("op") == "add":
                if str(op.get("data_type", "")).casefold() in changed_structures:
                    raise BridgeError("Editing a structure and adding a reference to it in one batch is unsupported.")
                require_new_identifier(op.get("name"), existing_names=global_names if suffix == ".gvt" else local_names,
                                       project_names=project_names if suffix == ".gvt" else ())
                (global_names if suffix == ".gvt" else local_names).add(op["name"])
    builder = candidate_builder or default_candidate_builder
    candidates = []
    for entry, source in entries:
        try:
            result = builder(entry, blobs[entry["file"]], source, definitions)
        except FormatRejection as exc:
            exc.context.setdefault("target", entry["file"])
            raise
        except ConflictError:
            raise
        except BridgeError as exc:
            raise FormatRejection(str(exc), code="offline_invalid_request", context={
                "target": entry["file"], "original_error": str(exc),
            }) from exc
        if not isinstance(result, bytes) or len(result) > st.MAX_NATIVE_SIZE:
            raise BridgeError("Candidate builder must return bounded bytes.")
        if Path(entry["file"]).suffix.lower() == ".fb":
            st.validate_program_edit(fb.parse(result).source)
        elif Path(entry["file"]).suffix.lower() == ".fc":
            st.validate_program_edit(fc.parse(result).source)
        elif Path(entry["file"]).suffix.lower() == ".st":
            st.validate_program_edit(st.parse(result).source)
        elif Path(entry["file"]).suffix.lower() in {".stru", ".gvt"}:
            tables.parse(result, Path(entry["file"]).suffix.lower()[1:])
        elif Path(entry["file"]).suffix.lower() == ".fbi":
            instances.parse(result)
        candidates.append((entry["file"], result))
    if deleting:
        deletion_preflight.check(manifest, blobs, candidates, entries)
    return candidates


def build(workspace, changes_file, *, candidate_builder=None):
    workspace, manifest = _load(workspace)
    blobs = _assert_baseline(manifest)
    entries = _changes(workspace, changes_file, manifest)
    candidates = _qualify(manifest, blobs, entries, candidate_builder)
    _assert_baseline(manifest)
    directory = workspace / ("build-" + uuid.uuid4().hex)
    directory.mkdir()
    targets = []
    requests = []
    for index, ((name, data), (entry, source)) in enumerate(zip(candidates, entries)):
        filename = "candidate-{}.native".format(index)
        storage.write_new(directory / filename, data)
        targets.append(dict(file=name, candidate=filename, sha256=storage.sha256(data)))
        request = dict(entry)
        request.pop("source_file", None)
        if source is not None:
            source_name = "source-{}.st".format(index)
            storage.write_new(directory / source_name, source)
            request["frozen_source"] = source_name
            request["source_sha256"] = storage.sha256(source)
        requests.append(request)
    plan_data = dict(schema=1, workspace=str(workspace), targets=targets, requests=requests,
                     manifest_sha256=_digest(manifest), builder_profile="injected" if candidate_builder else "default")
    if _has_deletions(entries):
        plan_data["deletion_preflight_scope"] = deletion_preflight.SCOPE
        plan_data.update(reference_check="not_performed_by_design", compile_pending=True, cascade=False)
    plan = _seal(plan_data)
    storage.write_json_new(directory / "plan.json", plan)
    result = dict(status="built", plan=str(directory / "plan.json"), targets=targets,
                plan_sha256=storage.sha256((directory / "plan.json").read_bytes()),
                validation="candidate_only_reload_save_compile_pending")
    if _has_deletions(entries):
        result["deletion_preflight_scope"] = deletion_preflight.SCOPE
        result.update(reference_check="not_performed_by_design", compile_pending=True, cascade=False)
    return result


def _replace(target, expected, data):
    """Already backed up by the batch; stage durably and read back completely."""
    target = storage.writable_target(target)
    with storage.target_lock(target):
        storage.assert_hash(target, expected)
        fd, name = tempfile.mkstemp(prefix="." + target.name, suffix=".tmp", dir=str(target.parent))
        staged = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if staged.read_bytes() != data:
                raise BridgeError("Candidate staging verification failed.")
            os.chmod(staged, target.stat().st_mode)
            storage.assert_hash(target, expected)
            os.replace(str(staged), str(target))
            if target.read_bytes() != data:
                raise BridgeError("Written file readback differs.")
        finally:
            if staged.exists():
                staged.unlink()


def _execute(manifest, candidates, backup_root, *, guard_factory, reason, expected=None):
    project = Path(manifest["project"])
    backup_root = _outside(backup_root, project)
    expected = dict(expected or manifest["hashes"])
    receipt = dict(schema=1, status="stopped", project=str(project), manifest=manifest,
                   before_hashes=dict(expected), after_hashes=dict(expected), backups={}, written=[], attempted=[], reason=reason)
    run = None
    with guard_factory(_member(project, manifest["hcp"])) as locked_hcp:
        try:
            blobs = _assert_baseline(manifest, expected, locked_hcp)
            backup_root.mkdir(parents=True, exist_ok=True)
            run = backup_root / ("offline-" + uuid.uuid4().hex)
            run.mkdir()
            for name, data in blobs.items():
                receipt["backups"][name] = str(storage.create_backup(_member(project, name), data, run, reason))
            # All backups (including HCP) have been independently read back.
            _assert_baseline(manifest, expected, locked_hcp)
            for name, data in candidates.items():
                if name not in manifest["registered"] or manifest["registered"][name]["state"] != "present" or Path(name).suffix.lower() not in {".st", ".fb", ".fc", ".stru", ".gvt", ".fbi"}:
                    raise BridgeError("Candidate is not an authorized registered native target.")
                if storage.sha256(data) == expected[name]:
                    continue
                _assert_baseline(manifest, receipt["after_hashes"], locked_hcp)
                receipt["attempted"].append(name)
                try:
                    _replace(_member(project, name), expected[name], data)
                except (OSError, BridgeError):
                    # Replacement may have occurred before a failed readback.
                    # Record an exact candidate outcome if it can be established;
                    # otherwise keep the old expected hash so restore refuses it.
                    if inventory.bounded_read(_member(project, name)) == data:
                        receipt["written"].append(name)
                        receipt["after_hashes"][name] = storage.sha256(data)
                    raise
                receipt["written"].append(name)
                receipt["after_hashes"][name] = storage.sha256(data)
            _assert_baseline(manifest, receipt["after_hashes"], locked_hcp)
            receipt["status"] = "applied"
        except (OSError, BridgeError) as exc:
            receipt["status"] = "partial" if receipt["attempted"] else "stopped"
            receipt["error"] = str(exc)
            receipt["error_code"] = error_code(exc)
        if run is not None:
            receipt["backup_run"] = str(run)
            try:
                storage.write_json_new(run / "receipt.json", _seal(receipt))
                receipt["receipt"] = str(run / "receipt.json")
                receipt["receipt_sha256"] = storage.sha256((run / "receipt.json").read_bytes())
            except (OSError, BridgeError) as exc:
                receipt["status"] = "partial" if receipt["attempted"] else "stopped"
                receipt["error"] = "{} Receipt persistence failed: {}".format(receipt.get("error", ""), exc).strip()
                receipt["error_code"] = error_code(exc)
    receipt["validation"] = "disk_readback_only_reload_save_compile_pending"
    return receipt


def apply(plan_file, backup_root, *, guard_factory=None, candidate_builder=None, expected_plan_sha256=None):
    _no_links(plan_file)
    plan_file = storage.regular_file(Path(plan_file))
    plan_bytes = inventory.bounded_read(plan_file)
    if expected_plan_sha256 is not None and storage.sha256(plan_bytes) != expected_plan_sha256:
        raise ConflictError("Offline plan differs from the explicitly authorized build digest.")
    try:
        plan = json.loads(plan_bytes.decode("utf8"))
    except (UnicodeError, ValueError) as exc:
        raise BridgeError("Invalid offline plan JSON.") from exc
    if not isinstance(plan, dict):
        raise BridgeError("Offline plan must be a JSON object.")
    _verify(plan)
    if plan.get("schema") != 1:
        raise BridgeError("Unsupported offline plan.")
    if not isinstance(plan.get("targets"), list) or not 1 <= len(plan["targets"]) <= 100:
        raise BridgeError("Expected a nonempty bounded offline plan.")
    workspace, manifest = _load(plan["workspace"])
    if plan.get("manifest_sha256") != _digest(manifest):
        raise ConflictError("Workspace baseline differs from built plan.")
    if plan.get("builder_profile") != ("injected" if candidate_builder else "default"):
        raise BridgeError("Plan requires the same explicit candidate builder profile.")
    _outside(plan_file, Path(manifest["project"]))
    candidates = {}
    for row in plan["targets"]:
        if (not isinstance(row, dict) or set(row) != {"file", "candidate", "sha256"}
                or not all(isinstance(row[k], str) for k in row)):
            raise BridgeError("Invalid built candidate record.")
        name = row["file"]
        if name in candidates:
            raise BridgeError("Duplicate candidate target.")
        path = _member(plan_file.parent, row["candidate"])
        data = inventory.bounded_read(path)
        if storage.sha256(data) != row["sha256"]:
            raise ConflictError("Built candidate changed.")
        candidates[name] = data
    if not isinstance(plan.get("requests"), list) or len(plan["requests"]) != len(candidates):
        raise BridgeError("Built plan requires its complete frozen operations.")
    entries, seen = [], set()
    for request in plan["requests"]:
        if (not isinstance(request, dict) or "file" not in request
                or set(request) - {"file", "variable_operations", "frozen_source", "source_sha256"}
                or not isinstance(request["file"], str)):
            raise BridgeError("Invalid frozen offline request.")
        name = request["file"]
        if name not in manifest["registered"] or manifest["registered"][name]["state"] != "present" or name in seen:
            raise BridgeError("Frozen request target is not uniquely registered.")
        seen.add(name)
        entry = {k: v for k, v in request.items() if k not in {"frozen_source", "source_sha256"}}
        source = None
        if "frozen_source" in request:
            if not isinstance(request["frozen_source"], str):
                raise BridgeError("Invalid frozen source path.")
            source = inventory.bounded_read(_member(plan_file.parent, request["frozen_source"]))
            if storage.sha256(source) != request.get("source_sha256"):
                raise ConflictError("Frozen offline source changed.")
        if "variable_operations" in entry and not isinstance(entry["variable_operations"], list):
            raise BridgeError("Frozen variable operations must be a list.")
        if source is None and "variable_operations" not in entry:
            raise BridgeError("Frozen request is empty.")
        entries.append((entry, source))
    originals = {name: inventory.bounded_read(_member(workspace, filename)) for name, filename in manifest["originals"].items()}
    regenerated = dict(_qualify(manifest, originals, entries, candidate_builder))
    if regenerated != candidates:
        raise ConflictError("Candidate does not equal the fully rebuilt frozen request.")
    return _execute(manifest, candidates, backup_root, guard_factory=guard_factory or exclusive_hcp, reason="offline_apply")


def restore(receipt_file, backup_root, *, guard_factory=None, expected_receipt_sha256=None):
    _no_links(receipt_file)
    receipt_file = storage.regular_file(Path(receipt_file))
    receipt_bytes = inventory.bounded_read(receipt_file)
    if expected_receipt_sha256 is not None and storage.sha256(receipt_bytes) != expected_receipt_sha256:
        raise ConflictError("Offline receipt differs from the explicitly authorized apply digest.")
    try:
        receipt = json.loads(receipt_bytes.decode("utf8"))
    except (UnicodeError, ValueError) as exc:
        raise BridgeError("Invalid offline receipt JSON.") from exc
    if not isinstance(receipt, dict):
        raise BridgeError("Offline receipt must be a JSON object.")
    _verify(receipt)
    if receipt.get("schema") != 1 or receipt.get("status") not in {"applied", "partial"}:
        raise BridgeError("Expected an applied or partial offline receipt.")
    manifest = receipt["manifest"]
    _verify(manifest)
    _validate_manifest(manifest)
    _outside(receipt_file, Path(manifest["project"]))
    if (not isinstance(receipt.get("written"), list)
            or len(set(receipt["written"])) != len(receipt["written"])
            or not set(receipt["written"]) <= set(manifest["registered"])
            or set(receipt.get("before_hashes", {})) != set(manifest["hashes"])
            or set(receipt.get("after_hashes", {})) != set(manifest["hashes"])):
        raise BridgeError("Invalid offline recovery receipt.")
    candidates = {}
    for name in receipt["written"]:
        _no_links(receipt["backups"][name])
        backup = Path(receipt["backups"][name]).resolve(strict=True)
        if not _inside(backup, receipt_file.parent):
            raise BridgeError("Receipt backup escapes its batch directory.")
        data = inventory.bounded_read(_member(backup, "original.native"))
        metadata = storage.read_json(_member(backup, "backup.json"))
        if storage.sha256(data) != receipt["before_hashes"][name] or metadata["sha256"] != storage.sha256(data):
            raise ConflictError("Restore backup differs from recorded baseline.")
        candidates[name] = data
    return _execute(manifest, candidates, backup_root, guard_factory=guard_factory or exclusive_hcp,
                    reason="offline_restore", expected=receipt["after_hashes"])
