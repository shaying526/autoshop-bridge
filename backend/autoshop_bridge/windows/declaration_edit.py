"""Explicit declaration deletion, with an independently gated UI driver.

Empty layouts are gated by the pure candidate builder. No cascade, retry,
rollback, or implicit save.
FB, FC, structure, GVT and nonempty FBI menu profiles have desktop evidence.
"""

import copy
import struct
from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import declaration_delete, fb, fc, tables, instances
from autoshop_bridge.storage import assert_hash, create_backup, sha256, target_lock, write_json_new
from autoshop_bridge.windows.session import snapshot, assert_native_variables


VERIFIED_UI_KINDS = frozenset({"fb", "fc", "stru", "gvt", "fbi"})


def _disk_inventory(project):
    """Observe registration using the same scan policy as editor connections."""
    from autoshop_bridge.projects import inventory
    from autoshop_bridge.workflows import offline
    observed = inventory.scan(Path(project))
    root = Path(observed["project"])
    registration = []
    names = set()
    for row in observed["files"]:
        entry = {key: row.get(key) for key in
                 ("id", "name", "file", "file_type_raw", "program_type_raw", "path")}
        if "path" in row:
            path = Path(row["path"])
            entry["present"] = path.is_file()
            if entry["present"]:
                names.add(offline._member(root, path.relative_to(root).as_posix())
                          .relative_to(root).as_posix())
        registration.append(entry)
    # Include unregistered native files without interpreting their formats.
    for path in root.rglob("*"):
        offline._no_links(path)
        if path.is_file() and path.suffix.lower() in offline.NATIVE_SUFFIXES:
            names.add(offline._member(root, path.relative_to(root).as_posix())
                      .relative_to(root).as_posix())
    if len({name.casefold() for name in names}) != len(names):
        raise BridgeError("Protected project filenames collide under casefold comparison.")
    source = observed["registration_source"]
    if source["kind"] == "hcp":
        names.add(Path(observed["project_file"]).name)
    return observed, registration, sorted(names)


def preflight(project, target, kind, operations):
    """Freeze disk identities; references are intentionally left to AutoShop."""
    from autoshop_bridge.projects import inventory
    observed, registration, names = _disk_inventory(project)
    root = Path(observed["project"])
    target = Path(target).resolve()
    matches = [row for row in observed["files"]
               if row.get("path") and Path(row["path"]).resolve() == target]
    expected_kind = {"fb": "function_block", "fc": "function",
                     "stru": "structure", "gvt": "global_variables",
                     "fbi": "function_block_instances"}[kind]
    if (len(matches) != 1 or matches[0].get("kind") != expected_kind
            or matches[0].get("status") != "parsed"):
        raise BridgeError("Declaration deletion target must be exactly registered, parsed and present.")
    originals = {name: (inventory._read_hcp(root / name)
                        if name == Path(observed["project_file"]).name
                        else inventory.bounded_read(root / name)) for name in names}
    source = observed["registration_source"]
    if source["kind"] == "hcp" and sha256(originals[Path(observed["project_file"]).name]) != source["sha256"]:
        raise BridgeError("Declaration project registration changed during observation.")
    relative = target.relative_to(root).as_posix()
    if sha256(originals[relative]) != matches[0]["sha256"]:
        raise BridgeError("Declaration target changed during registration observation.")
    declaration_delete.rebuild(originals[relative], kind, operations)
    source = observed["registration_source"]
    # Embedded HCP hashes identify registration evidence only. Never put mirror
    # body bytes or an embedded HCP digest in a disk-file baseline.
    return dict(frozen_sources={str(root / n): sha256(raw) for n, raw in originals.items()},
                project=str(root), project_file=observed["project_file"],
                registration=registration, registration_source=source,
                protected_names=names,
                hcp_disk_observation=dict(readable=source["kind"] == "hcp",
                                          sha256=(source["sha256"] if source["kind"] == "hcp" else None)),
                reference_check="not_performed_by_design")


def _recheck_guard(guard, target):
    if "registration" in guard:
        observed, registration, names = _disk_inventory(guard["project_file"])
        old, new = guard["registration_source"], observed["registration_source"]
        if (registration != guard["registration"]
                or any(old.get(k) != new.get(k) for k in ("path", "kind", "member", "sha256"))):
            raise BridgeError("Declaration project registration changed.")
        if names != guard["protected_names"]:
            raise BridgeError("Declaration project file set changed.")
    for path, digest in guard["frozen_sources"].items():
        if Path(path).resolve() != target.resolve():
            if "registration" in guard and Path(path).resolve() == Path(guard["project_file"]).resolve():
                # _disk_inventory already checked the actual HCP through the
                # normal shared-read helper; do not reopen with weaker sharing.
                continue
            assert_hash(Path(path), digest)


def _parse(raw, kind):
    if kind == "fbi":
        return instances.parse(raw)
    return (fb if kind == "fb" else fc).parse(raw) if kind in ("fb", "fc") else tables.parse(raw, kind)


def verify_saved_bytes(candidate, actual, kind):
    """Require exact deletion bytes, allowing only observed zero FB row refresh."""
    if actual == candidate:
        return "exact"
    if kind != "fb":
        raise BridgeError("Saved declaration bytes differ from the exact candidate.")
    old, new = fb.parse(candidate), fb.parse(actual)
    def region(obj):
        start = obj.inner_offset + obj.inner.payload_offset + obj.inner.payload_length
        end = start + 8 + obj.inner.line_table_count * 16
        tail = obj.raw[start:end]
        zero, count = struct.unpack_from("<II", tail)
        expected = struct.pack("<II", 0, count) + b"".join(
            struct.pack("<IIII", i, 0, 0, 0) for i in range(count))
        if zero or tail != expected:
            raise BridgeError("Unknown nonzero FB line metadata changed during save.")
        return start, end
    a, b = region(old)
    c, d = region(new)
    if (old.line_table_count == new.line_table_count
            or new.line_table_count != new.source.count(b"\n") + 1
            or candidate[:a] != actual[:c] or candidate[b:] != actual[d:]):
        raise BridgeError("Saved FB changed outside the observed zero-field line-table refresh.")
    return "fb_zero_line_table_normalized"


def _snapshot(adapter, target):
    value = snapshot(adapter, target)
    if value["variables"] is None:
        value["variables"] = adapter.grid()
    return value


def _assert_same(a, b):
    if any(a[key] != b[key] for key in ("source", "variables", "native_sha256", "modified")):
        raise BridgeError("Declaration editor baseline changed.")


def _assert_native(raw, kind, rows):
    obj = _parse(raw, kind)
    if kind in ("fb", "fc"):
        assert_native_variables(obj, rows)
    elif kind == "fbi":
        from autoshop_bridge.windows.instance_session import assert_native
        assert_native(raw, rows)
    else:
        from autoshop_bridge.windows.table_session import assert_native_table
        assert_native_table(obj, rows)
    return obj


def _remaining(rows, name):
    result = copy.deepcopy([r for r in rows if r["name"] != name])
    if len(result) != len(rows) - 1:
        raise BridgeError("Expected one exact UI declaration name.")
    for index, row in enumerate(result):
        row["row"] = str(index + 1)
    return result


class NormalDeleteDriver:
    """Observed V4.11.0.5 declaration context-menu Delete Row (L) action."""

    def __init__(self, adapter, kind):
        self.a, self.kind = adapter, kind

    def validate(self):
        if self.kind not in VERIFIED_UI_KINDS:
            raise BridgeError("Normal declaration deletion UI profile is not verified for this kind.")
        a = self.a
        a.validate_main()
        if not a.text(a.main).startswith("AutoShop V4.11.0.5  "):
            raise BridgeError("Declaration delete requires the observed AutoShop V4.11.0.5.")
        from autoshop_bridge.windows.session import COLUMNS, FC_COLUMNS
        from autoshop_bridge.windows.table_session import STRUCT_COLUMNS, GLOBAL_COLUMNS
        from autoshop_bridge.windows.instance_session import INSTANCE_COLUMNS
        columns = {"fb": COLUMNS, "fc": FC_COLUMNS,
                   "stru": STRUCT_COLUMNS, "gvt": GLOBAL_COLUMNS,
                   "fbi": INSTANCE_COLUMNS}[self.kind]
        if a.columns != columns:
            raise BridgeError("Declaration delete columns differ from observed {} profile.".format(self.kind))
        a.assert_no_cell_edit()
        if self._owned_popups():
            raise BridgeError("Existing popup/dialog must be inspected before deletion.")

    def _owned_popups(self):
        a, found = self.a, []
        @a.callback_type
        def collect(hwnd, unused):
            if (hwnd != a.main and a.window_pid(hwnd) == a.pid
                    and a.user.IsWindowVisible(hwnd)
                    and a.user.GetParent(hwnd) == a.main):
                found.append(hwnd)
            return True
        if not a.user.EnumWindows(collect, 0):
            raise BridgeError("Cannot enumerate declaration context windows.")
        return found

    def delete_row(self, name, before):
        self.validate()
        a = self.a
        if a.grid() != before:
            raise BridgeError("UI changed before declaration deletion.")
        a.restore_for_cell_edit()
        a.activate()
        grid = a.variable_grid()
        if a.accessible("select_verified_cell", grid, variable=name,
                        column=a.columns["name"], expected=name) != "selection_verified":
            raise BridgeError("Declaration delete selection was not verified.")
        if a.grid() != before:
            raise BridgeError("Selecting declaration altered the grid.")
        if not a.user.PostMessageW(grid, 0x007B, grid, -1):
            raise BridgeError("Cannot open declaration row context menu.")
        state = {}
        def locate():
            windows = self._owned_popups()
            if not windows:
                return False
            if len(windows) != 1 or ":800:" not in a.class_name(windows[0]) or a.text(windows[0]):
                raise BridgeError("Unknown declaration popup; stopped without answering it.")
            state["popup"] = windows[0]
            return True
        a.wait_until(locate, "verified declaration row context menu")
        popup = state["popup"]
        a.post(popup, 0x100, ord("L"))
        a.post(popup, 0x101, ord("L"))
        desired = _remaining(before, name)
        def verify():
            windows = self._owned_popups()
            if windows == [popup]:
                return False  # Allow the already verified menu's posted key to run.
            if windows:
                raise BridgeError("Unknown prompt appeared after declaration deletion.")
            return a.grid() == desired
        a.wait_until(verify, "complete declaration deletion readback")
        return a.grid()


def edit_connected(adapter, target, opened, document, expected_sha256, *, kind,
                   project=None, save=False, dry_run=False, backup_root=None,
                   preflight=None, driver=None):
    """Injectable orchestration; caller's connection must establish registration."""
    target = Path(target)
    if target.suffix.lower() != "." + kind:
        raise BridgeError("Declaration target kind differs from requested kind.")
    if not isinstance(document, dict) or set(document) != {"schema", "operations"} or document["schema"] != 1:
        raise BridgeError("Declaration delete requires schema=1 and operations only.")
    if preflight is None:
        preflight = globals()["preflight"]
    driver = driver or NormalDeleteDriver(adapter, kind)
    with target_lock(target):
        raw = assert_hash(target, expected_sha256)
        candidate = declaration_delete.rebuild(raw, kind, document["operations"])
        before = _snapshot(adapter, target)
        obj = _assert_native(raw, kind, before["variables"])
        if before["modified"] or (kind in ("fb", "fc") and obj.source.decode("utf-8") != before["source"]):
            raise BridgeError("Dirty/cached declaration editor does not match native baseline.")
        guard = preflight(project or adapter.project, target, kind, document["operations"])
        def check_sources():
            _recheck_guard(guard, target)
        check_sources()
        if dry_run:
            return dict(status="declaration_delete_ready", target=str(target), opened=opened,
                        candidate_sha256=sha256(candidate),
                        preflight=dict(reference_check=guard.get("reference_check", "not_performed_by_design"),
                                       protected_count=len(guard["frozen_sources"]),
                                       registration_source={key: value for key, value in
                                           guard.get("registration_source", {}).items() if key in
                                           ("path", "kind", "member", "sha256", "possibly_stale",
                                            "hcp_read_reason", "hcp_winerror")}))
        driver.validate()
        saved = create_backup(target, raw, backup_root, "editor_declaration_delete")
        write_json_new(saved / "editor_before.json", before)
        write_json_new(saved / "deletion_preflight.json", guard)
        _assert_same(before, _snapshot(adapter, target))
        assert_hash(target, expected_sha256)
        check_sources()
        result = dict(status="declaration_delete_started", target=str(target), backup=str(saved),
                      opened=opened, completed_operations=[], save_requested=save,
                      autoshop_compile_verified=False, automatic_retry=False,
                      reference_check="not_performed_by_design")
        current = before["variables"]
        stage = "before_delete"
        try:
            for op in document["operations"]:
                assert_hash(target, expected_sha256)
                check_sources()
                if adapter.read().source.decode("utf-8") != before["source"]:
                    raise BridgeError("Declaration deletion changed editor body.")
                stage = "delete:" + op["name"]
                desired = _remaining(current, op["name"])
                actual = driver.delete_row(op["name"], current)
                if actual != desired or adapter.grid() != desired:
                    raise BridgeError("Full surviving declaration grid differs after deletion.")
                current = desired
                result["completed_operations"].append(op["name"])
            stage = "verify_buffer"
            after = _snapshot(adapter, target)
            if after["variables"] != current or after["source"] != before["source"] or not after["modified"]:
                raise BridgeError("Declaration final buffer verification failed.")
            assert_hash(target, expected_sha256)
            check_sources()
            write_json_new(saved / "editor_expected.json", after)
            result.update(status="declarations_updated_not_saved", requires_manual_save=True)
            if save:
                stage = "save_dispatched"
                adapter.save()
                stage = "verify_saved"
                actual = target.read_bytes()
                normalization = verify_saved_bytes(candidate, actual, kind)
                final = _snapshot(adapter, target)
                if final["modified"] or final["variables"] != current or final["source"] != before["source"]:
                    raise BridgeError("Saved declaration editor baseline differs.")
                _assert_native(actual, kind, current)
                check_sources()
                result.update(status="declarations_saved_verified", sha256=sha256(actual),
                              requires_manual_save=False, native_validation=normalization)
            result.update(stage="complete", declaration_count=len(current))
            write_json_new(saved / "declaration_result.json", result)
            return result
        except (BridgeError, OSError) as exc:
            result.update(status="declaration_delete_failed", stage=stage, error=str(exc),
                          recovery="Inspect current editor and backup; no automatic retry or rollback.")
            write_json_new(saved / "declaration_failure.json", result)
            raise BridgeError("Declaration deletion stopped at {}; backup {}; {}".format(stage, saved, exc)) from exc


def edit(project, program, document, expected_sha256, *, kind="fb", pid=None,
         open_if_missing=False, save=False, dry_run=False, backup_root=None):
    if kind not in ("fb", "fc", "stru", "gvt", "fbi"):
        raise BridgeError("Declaration deletion supports FB/FC/STRU/GVT/FBI only.")
    if kind == "fbi":
        from autoshop_bridge.windows.instance_session import connect
        adapter, target, opened, _ = connect(project, program, pid, open_if_missing)
    elif kind in ("fb", "fc"):
        from autoshop_bridge.windows.session import connect
        adapter, target, opened = connect(project, program, pid, open_if_missing)
    else:
        from autoshop_bridge.workflows.tables import connect
        adapter, target, opened = connect(project, program, pid, open_if_missing)
    return edit_connected(adapter, target, opened, document, expected_sha256,
                          kind=kind, project=project, save=save, dry_run=dry_run,
                          backup_root=backup_root)
