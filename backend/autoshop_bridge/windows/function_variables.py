"""Six-column FC edits; no invented initializer or retention state."""

import copy

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import fc
from autoshop_bridge.formats.tables import identifier
from autoshop_bridge.projects.identifiers import precheck_addition_names
from autoshop_bridge.storage import assert_hash, create_backup, target_lock, write_json_new
from autoshop_bridge.windows.session import assert_clean_native, snapshot, verify_saved


def validate(document, rows):
    from autoshop_bridge.windows.variables import validate_value

    precheck_addition_names(document)
    if not isinstance(document, dict) or set(document) != {"schema", "operations"} or document["schema"] != 1:
        raise BridgeError("FC changes require schema=1 and operations.")
    operations = document["operations"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit FC operations.")
    planned = copy.deepcopy(rows)
    for op in operations:
        if not isinstance(op, dict):
            raise BridgeError("FC operation must be an object.")
        if op.get("op") == "set":
            if set(op) != {"op", "name", "field", "expected", "value"} or op["field"] != "comment":
                raise BridgeError("FC set only supports comment; no initializer/retention columns exist.")
            matches = [r for r in planned if r["name"] == op["name"]]
            if len(matches) != 1 or not isinstance(op["expected"], str) or matches[0]["comment"] != op["expected"]:
                raise BridgeError("FC variable comment baseline differs.")
            validate_value("comment", op["value"], matches[0])
            matches[0]["comment"] = op["value"]
        elif op.get("op") == "add":
            if set(op) != {"op", "name", "data_type", "category", "initial_value", "comment"}:
                raise BridgeError("FC add requires name/category/data_type/initial_value/comment.")
            if (not identifier(op["name"]) or op["category"] not in ("VAR", "IN", "OUT", "INOUT")
                    or op["data_type"] not in ("BOOL", "INT", "DINT") or op["initial_value"] is not None
                    or any(r["name"].casefold() == op["name"].casefold() for r in planned)
                    or len(planned) >= 4096):
                raise BridgeError("FC additions require unique scalar variables and initial_value=null.")
            validate_value("comment", op["comment"], {})
            planned.append(dict(name=op["name"], data_type=op["data_type"], category=op["category"], comment=op["comment"]))
        else:
            raise BridgeError("FC operation unsupported; deletion/type/return-type changes are pending.")
    return operations


def edit_connected(adapter, target, opened, document, expected, save, close_after,
                   dry_run, backup_root):
    with target_lock(target):
        raw = assert_hash(target, expected.lower())
        original = assert_clean_native(adapter, target, raw)
        before = snapshot(adapter, target)
        operations = validate(document, before["variables"])
        additions = [op for op in operations if op["op"] == "add"]
        if dry_run:
            return dict(status="variables_ready", operations=operations, variable_count=len(before["variables"]),
                        selector_preflight="pending_first_default_row" if additions and not before["variables"]
                        else "not_performed")
        if all(op["op"] == "set" and op["expected"] == op["value"] for op in operations):
            if close_after:
                adapter.close()
            return dict(status="unchanged_closed" if close_after else "unchanged",
                        target=str(target), variable_count=len(before["variables"]))
        saved = create_backup(target, raw, backup_root, "fc_editor_variables")
        write_json_new(saved / "editor_before.json", before)
        write_json_new(saved / "variable_changes.json", document)
        again = snapshot(adapter, target)
        if any(again[k] != before[k] for k in ("source", "variables", "native_sha256", "modified")):
            raise BridgeError("FC changed during variable backup.")
        assert_hash(target, expected.lower())
        current = copy.deepcopy(before["variables"])

        def check_body_and_disk():
            if adapter.read().source.decode("utf-8") != before["source"]:
                raise BridgeError("FC variable edit changed body.")
            assert_hash(target, expected.lower())

        def set_field(name, field, old, value):
            nonlocal current
            desired = copy.deepcopy(current)
            next(r for r in desired if r["name"] == name)[field] = value
            if desired == current:
                return
            actual = adapter.set_cell(name, field, old, value)
            if actual != desired:
                raise BridgeError("FC full-table readback differs after edit.")
            current = actual
            check_body_and_disk()

        def inspect_selectors(probe):
            types = adapter.selector_choices(probe["name"], "data_type", probe["data_type"])
            categories = adapter.selector_choices(probe["name"], "category", probe["category"])
            if categories != ["VAR", "IN", "OUT", "INOUT"] or any(types.count(op["data_type"]) != 1 for op in additions):
                raise BridgeError("FC type/category selector differs.")

        try:
            deferred_selector = bool(additions and not current)
            if additions and current:
                probe = next((r for r in current if r["data_type"] in ("BOOL", "INT", "DINT")), None)
                if probe is None:
                    raise BridgeError("A scalar FC row is required for type-selector preflight.")
                inspect_selectors(probe)
                again = snapshot(adapter, target)
                if any(again[k] != before[k] for k in ("source", "variables", "native_sha256", "modified")):
                    raise BridgeError("FC selector inspection changed the document.")
            for op in operations:
                if op["op"] == "add":
                    actual = adapter.set_cell("#row:" + str(len(current) + 1), "name", "", op["name"])
                    if actual[:-1] != current or len(actual) != len(current) + 1:
                        raise BridgeError("FC addition changed existing rows/count.")
                    row = actual[-1]
                    if (set(row) != {"row", "name", "category", "data_type", "comment", "id"}
                            or row["name"] != op["name"] or row["category"] != "VAR"
                            or row["data_type"] != "BOOL" or row["comment"] != ""
                            or row["row"] != str(len(actual)) or not row["id"]):
                        raise BridgeError("FC new variable defaults differ.")
                    current = actual
                    check_body_and_disk()
                    if deferred_selector:
                        # The real selector does not exist until the IDE creates
                        # its first default row. Failure retains that known dirty
                        # row; never save, repeat the add, or silently discard it.
                        inspect_selectors(row)
                        observed = snapshot(adapter, target)
                        if (observed["variables"] != current or observed["source"] != before["source"]
                                or observed["native_sha256"] != before["native_sha256"]
                                or not observed["modified"]):
                            raise BridgeError("FC first-row selector changed the verified buffer or disk.")
                        deferred_selector = False
                    set_field(op["name"], "category", "VAR", op["category"])
                    set_field(op["name"], "data_type", "BOOL", op["data_type"])
                    set_field(op["name"], "comment", "", op["comment"])
                else:
                    set_field(op["name"], "comment", op["expected"], op["value"])
            after = snapshot(adapter, target)
            if (after["variables"] != current or not after["modified"]
                    or after["source"] != before["source"] or after["native_sha256"] != before["native_sha256"]):
                raise BridgeError("FC dirty-state/full-table verification failed.")
            write_json_new(saved / "editor_expected.json", after)
            result = dict(status="variables_updated_not_saved", target=str(target), backup=str(saved),
                          variable_count=len(current), opened=opened, requires_manual_save=True,
                          autoshop_compile_verified=False, initialization_scope="FC has no initializer/retention columns")
            if save:
                adapter.save()
                digest = verify_saved(adapter, target, after)
                obj = fc.parse(assert_hash(target, digest))
                for old, new in zip(original.variables, obj.variables):
                    if (old.name, old.type_text, old.type_code, old.fields) != (new.name, new.type_text, new.type_code, new.fields):
                        raise BridgeError("FC save changed original variable definitions/opaque fields.")
                result.update(status="variables_saved", sha256=digest, requires_manual_save=False)
                if close_after:
                    adapter.close()
                    result["status"] = "variables_saved_closed"
            write_json_new(saved / "variable_result.json", result)
            return result
        except (BridgeError, OSError) as exc:
            raise BridgeError("{} FC buffer or saved file may have changed; inspect AutoShop. Backup: {}".format(exc, saved)) from exc
