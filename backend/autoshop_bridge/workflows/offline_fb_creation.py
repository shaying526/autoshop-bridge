"""Closed-project creation with explicit planning and durable recovery evidence."""

import os
import stat
import uuid
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from autoshop_bridge import storage
from autoshop_bridge.errors import BridgeError, ConflictError
from autoshop_bridge.formats import fb
from autoshop_bridge.projects import inventory, litest_registration
from autoshop_bridge.projects.offline_guard import error_code, exclusive_project_file, read_locked
from autoshop_bridge.workflows.offline import _no_links, _outside, _registered, _seal, _verify


def _project(path):
    _no_links(path)
    hcp = inventory.select_project(Path(path))
    if inventory.select_project(hcp.parent) != hcp:
        raise BridgeError("Expected one exact HCP in the project directory.")
    return hcp


def _snapshot(hcp, locked):
    """Hash all regular project files. The HCP/folder bytes use their held handles."""
    root = hcp.parent
    hashes = {}
    for path in sorted(root.rglob("*")):
        _no_links(path)
        if path.is_dir():
            continue
        if not path.is_file():
            raise BridgeError("Unexpected project entry: {}".format(path))
        name = path.relative_to(root).as_posix()
        raw = locked[name] if name in locked else inventory.bounded_read(path)
        hashes[name] = storage.sha256(raw)
    if len({name.casefold() for name in hashes}) != len(hashes):
        raise BridgeError("Project filenames collide under casefold comparison.")
    return hashes


def _candidates(hcp, original, files, name, comment, stamp):
    if not isinstance(comment, str) or any(ord(c) < 32 for c in comment) or "*)" in comment or "(*" in comment:
        raise BridgeError("Provide one line of plain comment text without delimiters.")
    try:
        source = ("(* " + comment + " *)").encode("utf-8") if comment else b""
    except UnicodeError as exc:
        raise BridgeError("Invalid UTF-8 comment text.") from exc
    if len(source) > 4096:
        raise BridgeError("Initial FB comment exceeds 4096 UTF-8 bytes.")
    raw_fb = fb.new_litest(name, source)
    filename = name + ".FB"
    if any(Path(path).parent == Path(".") and Path(path).stem.casefold() == name.casefold() for path in files):
        raise ConflictError("An existing root file already uses the requested name.")
    _registered(hcp.parent, original[hcp.name])
    raw_hcp, raw_folder, row_id = litest_registration.add_litest(
        original[hcp.name], original["folder.txt"], name, stamp
    )
    return {filename: raw_fb, "folder.txt": raw_folder, hcp.name: raw_hcp}, row_id


def plan(project, name, comment, output):
    hcp = _project(project)
    folder = hcp.parent / "folder.txt"
    _no_links(folder)
    output = _outside(output, hcp.parent)
    stamp = datetime.now().strftime(litest_registration.STAMP_FORMAT)
    with exclusive_project_file(hcp) as hcp_handle, exclusive_project_file(folder) as folder_handle:
        original = {hcp.name: read_locked(hcp_handle), folder.name: read_locked(folder_handle)}
        files = _snapshot(hcp, original)
        candidates, row_id = _candidates(hcp, original, files, name, comment, stamp)
        if _snapshot(hcp, original) != files:
            raise ConflictError("Project changed during LiteST creation preflight.")
        expected = {key: storage.sha256(data) for key, data in candidates.items()}
        value = _seal(dict(schema=1, profile=litest_registration.PROFILE, project=str(hcp), name=name,
                           comment=comment, stamp=stamp, files=files, candidates=expected, registration_id=row_id))
        storage.write_json_new(output, value)
    return dict(status="offline_fb_ready", plan_file=str(output), plan_sha256=storage.sha256(output.read_bytes()),
                registration_id=row_id, protected_files=len(files), candidate_sha256=expected)


def _write_existing(stream, data):
    stream.seek(0)
    if stream.write(data) != len(data):
        raise BridgeError("Incomplete write to guarded registration file.")
    stream.truncate()
    stream.flush()
    os.fsync(stream.fileno())
    if read_locked(stream) != data:
        raise BridgeError("Guarded registration file failed complete readback.")


def _observed_files(hcp, candidates, files, handles):
    states = {}
    for name, expected in candidates.items():
        path = hcp.parent / name
        try:
            raw = read_locked(handles[name]) if name in handles else inventory.bounded_read(path)
        except FileNotFoundError:
            states[name] = {"state": "absent"}
        except (BridgeError, OSError) as exc:
            states[name] = {"state": "unreadable", "error": str(exc)}
        else:
            digest = storage.sha256(raw)
            state = "candidate" if raw == expected else "original" if digest == files.get(name) else "other"
            states[name] = {"state": state, "sha256": digest}
    return states


def apply(plan_file, expected_plan_sha256, backup_root):
    _no_links(plan_file)
    plan_file = storage.regular_file(Path(plan_file))
    raw_plan = storage.assert_hash(plan_file, expected_plan_sha256)
    value = storage.read_json(plan_file)
    if plan_file.read_bytes() != raw_plan:
        raise ConflictError("LiteST creation plan changed during read.")
    _verify(value)
    if (set(value) != {"schema", "profile", "project", "name", "comment", "stamp", "files", "candidates",
                       "registration_id", "integrity_sha256"} or value["schema"] != 1
            or value["profile"] != litest_registration.PROFILE or not isinstance(value["project"], str)
            or not Path(value["project"]).is_absolute()):
        raise BridgeError("Unsupported LiteST creation plan.")
    hcp = _project(value["project"])
    if str(hcp) != value["project"]:
        raise ConflictError("LiteST creation project path differs.")
    _outside(plan_file, hcp.parent)
    backup_root = _outside(backup_root, hcp.parent)
    folder = hcp.parent / "folder.txt"
    _no_links(folder)
    for path in (hcp, folder):
        if not path.stat().st_mode & stat.S_IWRITE:
            raise BridgeError("Registration file is read-only: {}".format(path))
    with ExitStack() as locks:
        handles = {path.name: locks.enter_context(exclusive_project_file(path, writable=True)) for path in (hcp, folder)}
        original = {name: read_locked(stream) for name, stream in handles.items()}
        files = _snapshot(hcp, original)
        if files != value["files"]:
            raise ConflictError("Project files differ from the reviewed LiteST creation plan.")
        candidates, row_id = _candidates(hcp, original, files, value["name"], value["comment"], value["stamp"])
        hashes = {name: storage.sha256(raw) for name, raw in candidates.items()}
        if hashes != value["candidates"] or row_id != value["registration_id"]:
            raise ConflictError("Rebuilt LiteST creation candidates differ from the plan.")
        filename = value["name"] + ".FB"
        target = hcp.parent / filename
        run = backup_root / ("offline-fb-" + uuid.uuid4().hex)
        run.mkdir(parents=True)
        backups = {name: str(storage.create_backup(hcp.parent / name, raw, run, "offline_litest_create", hashes[name]))
                   for name, raw in original.items()}
        storage.write_new(run / "plan.json", raw_plan)
        storage.write_json_new(run / "intent.json", dict(project=str(hcp), absent_before=filename,
                              backups=backups, candidate_sha256=hashes, plan_sha256=expected_plan_sha256))
        if _snapshot(hcp, original) != files:
            raise ConflictError("Project changed while preparing LiteST creation backups.")

        result = dict(status="offline_fb_created", project=str(hcp), native_path=str(target),
                      registration_id=row_id, backup_run=str(run), non_targets_verified=False)
        attempted = []
        try:
            # Publish the body first. The HCP is the last write and remains
            # exclusively held, so AutoShop cannot load intermediate registration.
            storage.write_new(target, candidates[filename])
            handles[filename] = locks.enter_context(exclusive_project_file(target))
            if read_locked(handles[filename]) != candidates[filename]:
                raise ConflictError("New native FB changed before registration.")
            for name in (folder.name, hcp.name):
                attempted.append(name)
                _write_existing(handles[name], candidates[name])
            current = {name: read_locked(stream) for name, stream in handles.items()}
            registered = _registered(hcp.parent, current[hcp.name])
            if (registered[filename]["name"] != value["name"] or registered[filename]["file_type_raw"] != "81"
                    or _snapshot(hcp, current) != dict(files, **hashes)):
                raise ConflictError("Created FB, registration or non-target file readback differs.")
            result["non_targets_verified"] = True
        except (OSError, BridgeError) as exc:
            # Restore only files on our still-exclusive handles. If a newly
            # created FB exists, leave it visible in the receipt for recovery.
            failures = {}
            for name in reversed(attempted):
                try:
                    _write_existing(handles[name], original[name])
                except (OSError, BridgeError) as recovery_error:
                    failures[name] = str(recovery_error)
            result.update(status="stopped", error=str(exc), error_code=error_code(exc),
                          rollback_errors=failures)
        result["landed"] = _observed_files(hcp, candidates, files, handles)
        result["pair_verified"] = result["non_targets_verified"] and all(
            item["state"] == "candidate" for item in result["landed"].values())
        if result["status"] == "stopped" and any(item["state"] not in ("original", "absent")
                                                 for item in result["landed"].values()):
            result["status"] = "partial"
        try:
            receipt = run / "receipt.json"
            storage.write_json_new(receipt, result)
            result["receipt"] = str(receipt)
        except (OSError, BridgeError) as exc:
            result.update(status="partial", receipt_error=str(exc))
        return result
