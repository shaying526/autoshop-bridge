"""Existing FBI fields through the IDE, with complete source-side protection."""

import copy
import re
from collections import Counter
from pathlib import Path

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import native, instances
from autoshop_bridge.formats.offline_instances import edit_fields
from autoshop_bridge.storage import (
    assert_hash, create_backup, read_json, sha256, target_lock,
    writable_target, write_json_new,
)
from autoshop_bridge.windows import instance_session as ui


def _document(value):
    if (not isinstance(value, dict) or set(value) != {"schema", "operations"}
            or value["schema"] != 1):
        raise BridgeError("FBI field edits require schema=1 and operations only.")
    operations = value["operations"]
    if (not isinstance(operations, list) or not 1 <= len(operations) <= 32
            or any(not isinstance(op, dict) or op.get("op") != "set" for op in operations)):
        raise BridgeError("Expected 1..32 explicit existing FBI field edits.")
    for op in operations:
        if op.get("field") == "initial_value":
            if "member" not in op:
                raise FormatRejection(
                    "Editor initial values require an explicit displayed member path; full native strings use the closed-project offline workflow.",
                    code="fbi_editor_initializer_not_implemented",
                    context=dict(field="initial_value", supported_editor_form="member/expected/value",
                                 supported_file_workflow="offline-export/check/build/apply"))
            if (set(op) != {"op", "name", "field", "member", "expected", "value"}
                    or any(not isinstance(op.get(key), str) for key in ("name", "member", "expected", "value"))
                    or not op["member"] or any("\0" in op[key] for key in ("member", "expected", "value"))):
                raise BridgeError("Editor initial values require exact name/member/expected/value strings.")
            try:
                op["member"].encode("utf-8"); op["expected"].encode("utf-8"); op["value"].encode("utf-8")
            except UnicodeError as exc:
                raise BridgeError("Invalid Unicode in instance initial-value edit.") from exc
            ui.initial_member_paths([op["member"]])
        elif (set(op) != {"op", "name", "field", "expected", "value"}
              or op.get("field") not in ("name", "comment")):
            raise BridgeError("FBI editor fields are name/comment or initial_value with an explicit member path.")
    return operations


def _member_row(rows, instance, member):
    full = (instance + "." + member).casefold()
    found = [row for row in rows[1:] if row["full_name"].casefold() == full]
    if len(found) != 1:
        raise BridgeError("Expected one displayed instance initial-value member: " + member)
    return found[0]


def _assert_initial_root(rows, expected):
    root = rows[0]
    if (root["name"] != expected["name"] or root["data_type"].casefold() != expected["data_type"].casefold()
            or root["comment"] != ui.comment_display(expected["comment"])):
        raise BridgeError("Initial-value toolbox root differs from the exact FBI declaration.")
    address = expected.get("allocated_address")
    if address is None:
        raw_address = expected["uninterpreted_metadata"]["address_raw"]
        address = "" if raw_address == 0xFFFFFFFF else hex(raw_address)
    try:
        if ((not address and root["allocated_address"])
                or (address and int(root["allocated_address"], 16) != int(address, 16))):
            raise BridgeError("Initial-value toolbox allocation differs from the FBI declaration.")
    except ValueError as exc:
        raise BridgeError("Unsupported initial-value toolbox allocation display.") from exc


def _preflight_members(adapter, raw, operations):
    native_rows = {row["name"]: row for row in instances.parse(raw)["instances"]}
    identities = {name: name for name in native_rows}
    observed, baselines, paths = {}, {}, {}
    # Resolve every rename before the first toolbox collection: later requests
    # must not add newly displayed members during a write/readback comparison.
    for op in operations:
        if op["name"] not in identities:
            raise BridgeError("Expected one exact current FBI instance name.")
        original = identities[op["name"]]
        if op["field"] == "name":
            del identities[op["name"]]
            identities[op["value"]] = original
        elif op["field"] == "initial_value":
            paths.setdefault(original, []).append(op["member"])
    paths = {name: ui.initial_member_paths(value) for name, value in paths.items()}
    identities = {name: name for name in native_rows}
    for op in operations:
        if op["name"] not in identities:
            raise BridgeError("Expected one exact current FBI instance name.")
        original = identities[op["name"]]
        if op["field"] == "name":
            del identities[op["name"]]
            identities[op["value"]] = original
        elif op["field"] == "initial_value":
            if original not in observed:
                observed[original] = copy.deepcopy(_read_members(adapter, original, paths[original]))
                _assert_initial_root(observed[original], native_rows[original])
                baselines[original] = copy.deepcopy(observed[original])
            row = _member_row(observed[original], original, op["member"])
            ui.assert_initial_scalar(row, op["member"])
            if row["initial_value"] != op["expected"]:
                raise BridgeError("Instance initial-value member baseline differs: " + op["member"])
            row["initial_value"] = op["value"]
    return {name: dict(before=baselines[name], expected=rows, paths=paths[name]) for name, rows in observed.items()}


def _read_members(adapter, name, paths):
    try:
        if getattr(adapter, "initial_member_paths_supported", False):
            return adapter.initial_members(name, member_paths=paths)
        if any("." in path for path in paths):
            raise BridgeError("This editor adapter does not support explicit nested initial-value paths.")
        return adapter.initial_members(name)
    except BridgeError as exc:
        if not getattr(adapter, "physical_initial_selection", False):
            raise
        context = dict(getattr(exc, "context", {}))
        context.update(_physical_selection_details(adapter), automatic_retry=False)
        raise FormatRejection(str(exc), code=getattr(exc, "code", "physical_initial_read_stopped"), context=context) from exc


def _set_member(adapter, name, member, expected, value, paths):
    if getattr(adapter, "initial_member_paths_supported", False):
        return adapter.set_initial_member(name, member, expected, value, member_paths=paths)
    return adapter.set_initial_member(name, member, expected, value)


def _physical_selection_details(adapter):
    if not getattr(adapter, "physical_initial_selection", False):
        return {}
    receipts = copy.deepcopy(getattr(adapter, "initial_physical_selection_receipts", []))
    return dict(physical_selection=True, selection_mode="physical",
                physical_selection_receipt=receipts[-1] if receipts else None,
                physical_selection_receipts=receipts)


def _selection_baseline(adapter, rows, raw=None):
    if getattr(adapter, "physical_initial_selection", False):
        adapter.initial_selection_expected_rows = copy.deepcopy(rows)
        if raw is not None:
            adapter.initial_selection_native_sha256 = sha256(raw)
            adapter.initial_selection_native_names = [row["name"] for row in instances.parse(raw)["instances"]]


def _renamed_members(before, old, new, actual):
    """Permit only the requested instance prefix replacement.

    The IDE's full-name prefix is case insensitive (already checked by the
    reader); the suffix and every other field remain exact. Preserve the
    observed spelling only after verifying that precise replacement.
    """
    wanted = copy.deepcopy(before)
    if len(wanted) != len(actual):
        raise BridgeError("FBI rename changed the complete member collection.")
    wanted[0]["name"] = new
    for expected, observed in zip(wanted, actual):
        full = expected["full_name"]
        prefix, suffix = full[:len(old)], full[len(old):]
        replacement = observed["full_name"]
        if (prefix.casefold() != old.casefold() or replacement[:len(new)].casefold() != new.casefold()
                or replacement[len(new):] != suffix):
            raise BridgeError("FBI rename changed an unrequested member identity.")
        expected["full_name"] = replacement
    if actual != wanted:
        raise BridgeError("FBI rename changed unrequested initial-value member fields.")
    return wanted


def reference_changes(before, after, renames):
    """Verify IDE-produced name replacements, without requiring all references.

    Unchanged files are never parsed. A changed known source may change only
    identifier tokens requested by this rename; its native envelope must match
    the existing writer. No body is written or reference completeness proved.
    """
    result = []
    if set(before) != set(after):
        raise BridgeError("FBI editor changed the protected source file set.")
    for path, original in before.items():
        changed = after[path]
        if changed == original:
            continue
        kind = Path(path).suffix.lower()[1:]
        if not renames or kind not in ("st", "fb", "fc"):
            raise BridgeError("IDE changed an unsupported association: " + str(path))
        old, new = native.parse(original, kind), native.parse(changed, kind)
        a = re.split(r"(\w+)", old.source.decode("utf-8"))
        b = re.split(r"(\w+)", new.source.decode("utf-8"))
        if len(a) != len(b):
            raise BridgeError("IDE changed source beyond requested identifiers: " + str(path))
        count = 0
        for first, second in zip(a, b):
            if first == second:
                continue
            possible = {first}
            for name, value in renames:
                if any(item.casefold() == name.casefold() for item in possible):
                    possible.add(value)
            if not first.isidentifier() or second not in possible:
                raise BridgeError("IDE changed source beyond requested identifiers: " + str(path))
            count += 1
        if not count or old.rebuild(new.source) != changed:
            raise BridgeError("IDE changed unrelated native source metadata: " + str(path))
        result.append(dict(file=str(path), before_sha256=sha256(original),
                           after_sha256=sha256(changed), identifier_replacements=count))
    return result


def _freeze(project, target):
    from autoshop_bridge.windows.declaration_edit import _disk_inventory
    from autoshop_bridge.projects import inventory
    observed, registration, names = _disk_inventory(project)
    root = Path(observed["project"])
    # Actual HCP can be held by AutoShop; scan has already qualified the exact
    # registration evidence. Native sources are separately frozen byte-for-byte.
    sources = {str(root / name): inventory.bounded_read(root / name) for name in names
               if Path(name).suffix.lower() != ".hcp"}
    metadata = {}
    source = Path(observed["registration_source"]["path"])
    if source.suffix.lower() == ".hcpp":
        metadata[str(source)] = inventory.bounded_read(source)
    if str(target) not in sources:
        raise BridgeError("FBI target is outside the protected registered project.")
    names_in_scope = []
    for item in observed["files"]:
        if item.get("status") != "parsed":
            continue
        if item.get("kind") == "global_variables":
            names_in_scope.extend(row["name"] for row in item["table"]["rows"])
        elif item.get("kind") == "function_block_instances":
            names_in_scope.extend(row["name"] for row in item["instances"]["instances"])
    return dict(sources=sources, metadata=metadata, registration=registration,
                protected_names=names, project=str(root), names_in_scope=names_in_scope)


def _check_scope(guard):
    if "project" in guard:
        from autoshop_bridge.windows.declaration_edit import _disk_inventory
        _, registration, names = _disk_inventory(guard["project"])
        if registration != guard["registration"] or names != guard["protected_names"]:
            raise BridgeError("FBI project registration or protected file set changed.")


def _check_names(guard, operations):
    names = Counter(name.casefold() for name in guard.get("names_in_scope", []))
    for op in operations:
        if op["field"] == "name":
            names[op["name"].casefold()] -= 1
            if names[op["value"].casefold()] > 0:
                raise BridgeError("FBI rename conflicts with a known global declaration.")
            names[op["value"].casefold()] += 1


def _current(sources):
    return {path: Path(path).read_bytes() for path in sources}


def _assert_current(sources):
    if _current(sources) != sources:
        raise BridgeError("Protected project source changed during FBI editing.")


def edit_connected(adapter, target, opened, document, expected, *, guard,
                   save=False, close_after=False, dry_run=False, backup_root=None):
    operations = _document(document)
    target = Path(target)
    if dry_run and getattr(adapter, "physical_initial_selection", False):
        raise BridgeError("Dry run cannot request physical mouse selection.")
    if close_after and not save:
        raise BridgeError("--close requires --save.")
    if save:
        writable_target(target)
    with target_lock(target):
        raw = assert_hash(target, expected)
        native_ops = [op for op in operations if op["field"] != "initial_value"]
        candidate = edit_fields(raw, native_ops) if native_ops else raw
        _check_names(guard, operations)
        sources = dict(guard["sources"])
        if sources.get(str(target)) != raw:
            raise BridgeError("FBI source guard differs from target baseline.")
        before = ui.snapshot(adapter, target)
        if before["modified"]:
            raise BridgeError("FBI editor has unsaved changes.")
        ui.assert_native(raw, before["rows"])
        _selection_baseline(adapter, before["rows"], raw)
        member_preflight = _preflight_members(adapter, raw, operations)
        _check_scope(guard)
        _assert_current(sources)
        _check_scope(guard)
        edited = candidate != raw or any(op["field"] == "initial_value" and op["expected"] != op["value"] for op in operations)
        if dry_run:
            return dict(status="instances_edit_ready", edited=edited,
                        instance_count=len(before["rows"]), references="IDE may rename references; all native sources protected")
        if not edited:
            if close_after:
                adapter.close()
            return dict(status="unchanged_closed" if close_after else "unchanged", **_physical_selection_details(adapter))
        renaming = any(op["field"] == "name" and op["expected"] != op["value"] for op in operations)
        backups = {}
        protected = dict(sources, **guard.get("metadata", {})) if renaming else {str(target): raw}
        for path, data in protected.items():
            backups[path] = str(create_backup(Path(path), data, backup_root, "editor_fbi_fields"))
        backup = Path(backups[str(target)])
        write_json_new(backup / "editor_before.json", before)
        write_json_new(backup / "field_changes.json", document)
        write_json_new(backup / "protected_backups.json", backups)
        if ui.snapshot(adapter, target) != before:
            raise BridgeError("FBI editor changed during backup.")
        _assert_current(sources)
        current = copy.deepcopy(before["rows"])
        member_paths_by_index = {index: member_preflight[row["name"]]["paths"]
                                 for index, row in enumerate(current) if row["name"] in member_preflight}
        expected_members = {index: copy.deepcopy(member_preflight[row["name"]]["before"])
                            for index, row in enumerate(current) if row["name"] in member_preflight}
        updates, completed = [], []
        member_indices, member_results = set(), {}
        try:
            for operation in operations:
                _check_scope(guard)
                _assert_current(sources)
                name, field = operation["name"], operation["field"]
                old = ui.comment_display(operation["expected"]) if field == "comment" else operation["expected"]
                value = ui.comment_display(operation["value"]) if field == "comment" else operation["value"]
                desired = copy.deepcopy(current)
                if old == value:
                    continue
                index = next(i for i, row in enumerate(desired) if row["name"] == name)
                row = desired[index]
                if field == "initial_value":
                    paths = member_paths_by_index[index]
                    members = _read_members(adapter, name, paths)
                    _assert_initial_root(members, row)
                    if members != expected_members[index]:
                        raise BridgeError("FBI complete initial-value member baseline changed before edit.")
                    member = _member_row(members, name, operation["member"])
                    ui.assert_initial_scalar(member, operation["member"])
                    if member["initial_value"] != old:
                        raise BridgeError("FBI initial member changed before edit.")
                    wanted = copy.deepcopy(expected_members[index])
                    _member_row(wanted, name, operation["member"])["initial_value"] = value
                    actual_members = _set_member(adapter, name, operation["member"], old, value, paths)
                    if actual_members != wanted:
                        raise BridgeError("Full instance member readback differs after initial-value edit.")
                    expected_members[index] = wanted
                    actual = adapter.grid()
                    if len(actual) != len(desired):
                        raise BridgeError("FBI initial-value edit changed declaration count.")
                    row["initial_raw"] = actual[index]["initial_raw"]
                    member_indices.add(index)
                    member_results[(index, operation["member"].casefold())] = (operation["member"], value)
                else:
                    if row[field] != old:
                        raise BridgeError("FBI editor field baseline differs.")
                    row[field] = value
                    actual = adapter.set_cell(name, field, old, value)
                    if actual != desired:
                        raise BridgeError("FBI full-table readback differs after field edit.")
                    _selection_baseline(adapter, desired)
                    if index in expected_members:
                        # Declaration edits may rebuild the toolbox. Rebind all
                        # requested paths, permitting only explicit metadata edits.
                        members = _read_members(adapter, row["name"], member_paths_by_index[index])
                        if field == "name":
                            expected_members[index] = _renamed_members(expected_members[index], old, value, members)
                        else:
                            expected_members[index][0]["comment"] = value
                            if members != expected_members[index]:
                                raise BridgeError("FBI comment edit changed unrequested initial-value member fields.")
                if actual != desired:
                    raise BridgeError("FBI full-table readback differs after field edit.")
                _selection_baseline(adapter, desired)
                assert_hash(target, expected)
                others = {p: data for p, data in sources.items() if p != str(target)}
                after = _current(others)
                updates.extend(reference_changes(others, after, [(old, value)] if field == "name" else []))
                sources.update(after)
                _check_scope(guard)
                current = desired
                completed.append(operation)
            if adapter.grid() != current or not adapter.dirty():
                raise BridgeError("FBI final table/dirty state differs.")
            _assert_current(sources)
            write_json_new(backup / "editor_expected.json", dict(rows=current, reference_updates=updates))
            result = dict(status="instances_updated_not_saved", backup=str(backup),
                          protected_backups=backups, requires_manual_save=True,
                          target=str(target), opened=opened, instance_count=len(current),
                          reference_updates=updates, references_updated_by="AutoShop" if updates else None,
                          references_may_be_saved_before_target=renaming,
                          reference_completeness_checked=False, autoshop_compile_verified=False)
            if save:
                before_save_members = {}
                for index in sorted(expected_members):
                    before_save_members[index] = _read_members(adapter, current[index]["name"], member_paths_by_index[index])
                    _assert_initial_root(before_save_members[index], current[index])
                    if before_save_members[index] != expected_members[index]:
                        raise BridgeError("FBI complete initial-value member baseline changed before save.")
                for (index, _), (member, value) in member_results.items():
                    if _member_row(before_save_members[index], current[index]["name"], member)["initial_value"] != value:
                        raise BridgeError("Final initial-value member baseline differs before save.")
                adapter.save()
                saved = target.read_bytes()
                saved_rows = instances.parse(saved)["instances"]
                for index in sorted(member_indices):
                    candidate_row = instances.parse(candidate)["instances"][index]
                    original = instances.parse(raw)["instances"][index]
                    preflight = member_preflight[original["name"]]
                    if (preflight["before"] != preflight["expected"]
                            and saved_rows[index]["initial_value_raw"] == original["initial_value_raw"]):
                        raise BridgeError("Changed initial-value member was not persisted in the native initializer.")
                    candidate = edit_fields(candidate, [dict(op="set", name=candidate_row["name"], field="initial_value",
                        expected=candidate_row["initial_value_raw"], value=saved_rows[index]["initial_value_raw"])])
                if saved != candidate or adapter.dirty() or adapter.grid() != current:
                    raise BridgeError("Saved FBI differs from exact field candidate/table.")
                ui.assert_native(saved, current)
                _selection_baseline(adapter, current, saved)
                sources[str(target)] = saved
                _assert_current(sources)
                _check_scope(guard)
                result.update(status="instances_fields_saved", sha256=sha256(saved), requires_manual_save=False)
                if expected_members:
                    actual_members = {}
                    for index in sorted(expected_members):
                        name = current[index]["name"]
                        actual_members[index] = _read_members(adapter, name, member_paths_by_index[index])
                        _assert_initial_root(actual_members[index], current[index])
                        if actual_members[index] != before_save_members[index]:
                            raise BridgeError("Saved complete initial-value member collection differs.")
                    for (index, _), (member, value) in member_results.items():
                        if _member_row(actual_members[index], current[index]["name"], member)["initial_value"] != value:
                            raise BridgeError("Saved initial-value member readback differs.")
                    result["native_initializers"] = [dict(name=saved_rows[index]["name"], initial_value_raw=saved_rows[index]["initial_value_raw"])
                                                     for index in sorted(member_indices)]
                    write_json_new(backup / "saved_initial_members.json", {str(index): rows for index, rows in actual_members.items()})
                    _assert_current(sources)
                    _check_scope(guard)
                    if adapter.dirty():
                        raise BridgeError("Initial-value readback left unexpected unsaved contents.")
                if close_after:
                    adapter.close()
                    result["status"] = "instances_fields_saved_closed"
            result.update(_physical_selection_details(adapter))
            if getattr(adapter, "physical_initial_selection", False):
                write_json_new(backup / "physical_selection_receipts.json", result["physical_selection_receipts"])
            write_json_new(backup / "field_result.json", result)
            return result
        except (BridgeError, OSError) as exc:
            if getattr(adapter, "physical_initial_selection", False):
                write_json_new(backup / "physical_selection_failure_receipts.json", _physical_selection_details(adapter))
            write_json_new(backup / "field_failure.json", dict(error=str(exc), completed_operations=completed,
                           reference_updates=updates, automatic_retry=False, automatic_rollback=False))
            raise BridgeError("{} FBI buffer or associated sources may have changed; inspect backup {}.".format(exc, backup)) from exc


def edit(project, table, changes, expected, pid=None, open_if_missing=False,
         save=False, close_after=False, experimental=False, dry_run=False, backup_root=None, physical_select=False):
    from autoshop_bridge.workflows.declarations import validate_hash
    from autoshop_bridge.windows.project_lifecycle import WindowsProjectDriver
    validate_hash(expected)
    if type(physical_select) is not bool:
        raise BridgeError("physical_select must be an explicit boolean.")
    if physical_select and dry_run:
        raise BridgeError("Dry run cannot request physical mouse selection.")
    if not experimental and not dry_run:
        raise BridgeError("FBI editor modifications require --experimental.")
    if dry_run and open_if_missing:
        raise BridgeError("Dry run does not open tabs.")
    document = read_json(changes)
    _document(document)
    adapter, target, opened, inventory = ui.connect(project, table, pid, open_if_missing)
    adapter.physical_initial_selection = physical_select
    adapter.initial_physical_selection_receipts = []
    state = WindowsProjectDriver(Path(inventory["project_file"]), adapter.pid).snapshot()
    if any(state[key] for key in ("dirty", "cell_edits", "dialogs", "duplicates")):
        raise BridgeError("Project has unsaved contents, active cell edits or unknown dialogs.")
    guard = _freeze(project, target)
    return edit_connected(adapter, target, opened, document, expected.lower(), guard=guard,
                          save=save, close_after=close_after, dry_run=dry_run, backup_root=backup_root)


def read_initial(project, table, instance, pid=None, open_if_missing=False, output=None, *, member_paths=None, physical_select=False):
    """Observe actual selected-instance values, distinct from the saved string."""
    if not isinstance(instance, str) or not instance.isidentifier():
        raise BridgeError("Expected an exact instance identifier.")
    paths = ui.initial_member_paths(member_paths)
    if type(physical_select) is not bool:
        raise BridgeError("physical_select must be an explicit boolean.")
    adapter, target, opened, _ = ui.connect(project, table, pid, open_if_missing)
    adapter.physical_initial_selection = physical_select
    adapter.initial_physical_selection_receipts = []
    raw = target.read_bytes()
    native_rows = [row for row in instances.parse(raw)["instances"] if row["name"] == instance]
    members = _read_members(adapter, instance, paths)
    modified = adapter.dirty()
    if not modified and len(native_rows) == 1:
        _assert_initial_root(members, native_rows[0])
    result = dict(schema=1, status="instances_initial_read", source="editor_toolbox",
                  read_only=True, project=adapter.project, table=table, instance=instance,
                  target=str(target), pid=adapter.pid, opened=opened, modified=modified,
                  native_instance_verified=not modified and len(native_rows) == 1,
                  native_sha256=sha256(raw), native_initial_value_raw=native_rows[0]["initial_value_raw"] if len(native_rows) == 1 else None,
                  members=members, member_count=len(members)-1,
                  scope="currently displayed members of the exact selected instance",
                  selection_changed=True)
    result.update(_physical_selection_details(adapter))
    if member_paths is not None:
        result["requested_member_paths"] = list(paths)
        result["expansion_steps"] = copy.deepcopy(getattr(adapter, "last_initial_expansions", []))
    if hasattr(adapter, "last_initial_read"):
        result["collection"] = copy.deepcopy(adapter.last_initial_read)
    if target.read_bytes() != raw:
        raise BridgeError("FBI native source changed during initial-value read.")
    if output:
        write_json_new(output, result)
        summary = {key: result[key] for key in ("status", "instance", "member_count", "modified", "native_sha256")}
        summary["output"] = str(output.resolve())
        return summary
    return result
