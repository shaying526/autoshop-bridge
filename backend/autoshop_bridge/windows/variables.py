"""Narrow, explicit FB variable edits through the application, never raw patches."""

import copy
from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.fb import parse
from autoshop_bridge.formats.tables import identifier
from autoshop_bridge.projects import types as type_context
from autoshop_bridge.projects.identifiers import precheck_addition_names
from autoshop_bridge.windows.session import (
    assert_clean_native,
    connect,
    snapshot,
    verify_saved,
)
from autoshop_bridge.storage import (
    assert_hash,
    create_backup,
    read_json,
    sha256,
    target_lock,
    writable_target,
    write_json_new,
)


def validate_value(field, value, row):
    if (
        not isinstance(value, str)
        or any(ord(c) < 32 for c in value)
        or len(value.encode("utf-8")) > 4096
    ):
        raise BridgeError(
            "Variable values must be bounded strings without control characters."
        )
    if field == "comment":
        return
    if field != "initial_value":
        raise BridgeError(
            "Only comment and BOOL/INT/DINT initial_value edits are supported; other fields are pending."
        )
    if row["data_type"] == "BOOL" and value in ("OFF", "ON"):
        return
    if row["data_type"] in ("INT", "DINT"):
        bits = 16 if row["data_type"] == "INT" else 32
        try:
            number = int(value)
        except ValueError:
            number = None
        if (
            number is not None
            and -(2 ** (bits - 1)) <= number < 2 ** (bits - 1)
            and str(number) == value
        ):
            return
    raise BridgeError(
        "Unsupported scalar initial value/type; use BOOL OFF/ON or a canonical INT/DINT."
    )


def validate_changes(document, rows, types=None):
    precheck_addition_names(document)
    types = types or {}
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "operations"}
        or document["schema"] != 1
    ):
        raise BridgeError("Variable changes must contain schema=1 and operations.")
    operations = document["operations"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise BridgeError("Expected 1..32 explicit variable operations.")
    planned = copy.deepcopy(rows)
    for op in operations:
        if not isinstance(op, dict):
            raise BridgeError("Variable operation must be an object.")
        if op.get("op") == "set":
            if set(op) != {"op", "name", "field", "expected", "value"}:
                raise BridgeError("Set requires name, field, expected and value.")
            matches = [r for r in planned if r["name"] == op["name"]]
            if len(matches) != 1:
                raise BridgeError("Expected one exact variable name.")
            row = matches[0]
            if not isinstance(op["field"], str) or op["field"] not in (
                "comment",
                "initial_value",
            ):
                raise BridgeError(
                    "Unsupported variable field; only comment/initial_value are enabled."
                )
            if op["field"] == "initial_value" and row["category"] == "INOUT":
                raise BridgeError("INOUT has no independently editable initializer.")
            validate_value(op["field"], op["value"], row)
            if (
                not isinstance(op["expected"], str)
                or row[op["field"]] != op["expected"]
            ):
                raise BridgeError(
                    "Variable field baseline differs: {}.".format(op["name"])
                )
            row[op["field"]] = op["value"]
            if op["field"] == "initial_value":
                row["initial_raw"] = op["value"]
        elif op.get("op") == "add":
            if set(op) != {
                "op",
                "name",
                "data_type",
                "category",
                "initial_value",
                "comment",
            }:
                raise BridgeError(
                    "Add requires name, data_type, category, initial_value and comment."
                )
            if (
                not identifier(op["name"])
                or any(r["name"].casefold() == op["name"].casefold() for r in planned)
                or not isinstance(op["data_type"], str)
                or op["category"] not in ("VAR", "IN", "OUT", "INOUT")
            ):
                raise BridgeError("Invalid or duplicate variable definition.")
            code = type_context.SCALARS.get(
                op["data_type"], types.get(op["data_type"], {}).get("code")
            )
            if (
                code is None
                or (code == 256 and op["category"] != "VAR")
            ):
                raise BridgeError(
                    "Only scalar/structure variables and ordinary VAR FB instances are enabled."
                )
            default = op["category"] == "INOUT" or code in (64, 256)
            if default and op["initial_value"] is not None:
                raise BridgeError(
                    "INOUT/complex additions require initial_value=null (IDE defaults)."
                )
            row = {
                "row": str(len(planned) + 1),
                "name": op["name"],
                "data_type": op["data_type"],
                "category": op["category"],
                "initial_value": op["initial_value"],
                "initial_raw": op["initial_value"],
                "comment": op["comment"],
                "retention": "不保持",
                "id": None,
            }
            validate_value("comment", op["comment"], row)
            if not default:
                validate_value("initial_value", op["initial_value"], row)
            planned.append(row)
        else:
            raise BridgeError(
                "Unsupported variable operation; deletion, interfaces and type changes are pending."
            )
    return copy.deepcopy(operations)


def verify_native_preserved(before, after, operations, types=None, expected_rows=None):
    types = types or {}
    old, new = parse(before), parse(after)
    if old.source != new.source:
        raise BridgeError("Variable save unexpectedly changed FB body.")
    changes = {}
    added = []
    additions = {}
    for op in operations:
        if op["op"] == "set":
            changes[(op["name"], op["field"])] = op["value"]
        else:
            added.append(op["name"])
            additions[op["name"]] = op
    if [v.name for v in new.variables] != [v.name for v in old.variables] + added:
        raise BridgeError(
            "Saved variable ordering/names differ from requested changes."
        )
    for before_row, after_row in zip(old.variables, new.variables):
        for attr in ("type_text", "type_code", "name", "fields"):
            if getattr(before_row, attr) != getattr(after_row, attr):
                raise BridgeError(
                    "Unrequested native variable metadata changed: {}.".format(
                        before_row.name
                    )
                )
        if after_row.comment != changes.get(
            (before_row.name, "comment"), before_row.comment
        ):
            raise BridgeError("Saved native variable comment differs.")
        if after_row.initial_raw != changes.get(
            (before_row.name, "initial_value"), before_row.initial_raw
        ):
            raise BridgeError("Saved native variable initial value differs.")
    for var in new.variables[len(old.variables) :]:
        op = additions[var.name]
        code = type_context.SCALARS.get(
            op["data_type"], types.get(op["data_type"], {}).get("code")
        )
        initial = op["initial_value"]
        complex_default = initial is None and code in (64, 256)
        if initial is None and not complex_default:
            if expected_rows is None:
                raise BridgeError("IDE defaults require captured expected rows.")
            initial = next(r for r in expected_rows if r["name"] == var.name)[
                "initial_raw"
            ]
        if (
            var.type_code != code
            or (
                var.type_text != op["data_type"]
                if code in (64, 256)
                else var.type_text not in ("", op["data_type"])
            )
            or var.fields
            != (
                {"VAR": 0, "IN": 1, "OUT": 2, "INOUT": 3}[op["category"]],
                1,
                0xFFFFFFFF,
                0,
            )
            or var.comment != changes.get((var.name, "comment"), op["comment"])
            or (
                not complex_default
                and var.initial_raw != changes.get((var.name, "initial_value"), initial)
            )
        ):
            raise BridgeError(
                "Saved added variable type/category/value differs from requested definition."
            )


def edit(
    project,
    program,
    changes,
    expected,
    pid=None,
    open_if_missing=False,
    experimental=False,
    dry_run=False,
    save=False,
    close_after=False,
    backup_root=None,
):
    if close_after and not save:
        raise BridgeError(
            "--close requires --save; unsaved changes are never discarded."
        )
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(c not in "0123456789abcdefABCDEF" for c in expected)
    ):
        raise BridgeError("Expected SHA-256 must be 64 hexadecimal characters.")
    document = read_json(changes)
    if not experimental and not dry_run:
        raise BridgeError("Variable editing requires --experimental.")
    if dry_run and open_if_missing:
        raise BridgeError("--dry-run does not open tabs; use editor-open first.")
    precheck_addition_names(document)
    adapter, target, opened = connect(project, program, pid, open_if_missing)
    if target.suffix.lower() == ".fc":
        from autoshop_bridge.windows.function_variables import edit_connected
        if save:
            writable_target(target)
        return edit_connected(adapter, target, opened, document, expected, save,
                              close_after, dry_run, backup_root)
    if target.suffix.lower() != ".fb":
        raise BridgeError("Editor variable updates currently support FB only.")
    if save:
        writable_target(target)
    with target_lock(target):
        raw = assert_hash(target, expected.lower())
        before = snapshot(adapter, target)
        assert_clean_native(adapter, target, raw, observed=before)
        raw_ops = document.get("operations", [])
        requested = [
            op.get("data_type")
            for op in (raw_ops if isinstance(raw_ops, list) else [])
            if isinstance(op, dict)
            and op.get("op") == "add"
            and isinstance(op.get("data_type"), str)
        ]
        context = (
            type_context.catalog(project, requested, target.stem)
            if any(name not in type_context.SCALARS for name in requested)
            else dict(types={}, hashes={})
        )
        type_context.check(context)
        operations = validate_changes(document, before["variables"], context["types"])
        if dry_run:
            return dict(
                status="variables_ready",
                operations=operations,
                variable_count=len(before["variables"]),
            )
        if all(
            op["op"] == "set" and op["expected"] == op["value"] for op in operations
        ):
            if close_after:
                adapter.close()
                return dict(
                    status="unchanged_closed",
                    target=str(target),
                    variable_count=len(before["variables"]),
                )
            return dict(
                status="unchanged",
                target=str(target),
                variable_count=len(before["variables"]),
            )
        saved = create_backup(target, raw, backup_root, "editor_variables")
        write_json_new(saved / "editor_before.json", before)
        write_json_new(saved / "variable_changes.json", document)
        write_json_new(saved / "type_context.json", context)
        again = snapshot(adapter, target)
        for key in ("source", "variables", "native_sha256", "modified"):
            if again[key] != before[key]:
                raise BridgeError("Editor changed during variable backup.")
        assert_hash(target, expected.lower())
        current = copy.deepcopy(before["variables"])
        # Existing comments/scalar initializers do not change the table layout.
        # Keep per-cell identity/old-value/commit checks, then verify the entire
        # expected table once before saving. Adds and legacy adapters keep the
        # original per-field full-table checks.
        write_cell = getattr(adapter, "write_cell", None)
        deferred_sets = callable(write_cell) and all(
            op["op"] == "set" for op in operations
        )
        try:
            deferred_selector = bool(requested and not current)
            if requested and current:
                probe = next(
                    (r for r in current if r["data_type"] in type_context.SCALARS), None
                )
                if probe is None:
                    raise BridgeError(
                        "A scalar row is required for safe type-selector preflight."
                    )
                choices = adapter.selector_choices(
                    probe["name"], "data_type", probe["data_type"]
                )
                if any(choices.count(dtype) != 1 for dtype in requested):
                    raise BridgeError(
                        "Requested type is unavailable/ambiguous in the IDE selector."
                    )
                again = snapshot(adapter, target)
                if any(
                    again[k] != before[k]
                    for k in ("source", "variables", "native_sha256", "modified")
                ):
                    raise BridgeError("Type-selector preflight changed the document.")
            for op in operations:
                type_context.check(context)
                if op["op"] == "add":
                    new_row_number = str(len(current) + 1)
                    actual = adapter.set_cell(
                        "#row:" + new_row_number, "name", "", op["name"]
                    )
                    if actual[:-1] != current or len(actual) != len(current) + 1:
                        raise BridgeError(
                            "Variable addition changed existing rows/count."
                        )
                    new_row = actual[-1]
                    if (
                        new_row["name"] != op["name"]
                        or new_row["category"] != "VAR"
                        or new_row["data_type"] != "BOOL"
                        or new_row["retention"] != "不保持"
                        or new_row["initial_value"] != "OFF"
                        or new_row["comment"] != ""
                    ):
                        raise BridgeError(
                            "New variable defaults differ from the supported VAR BOOL profile."
                        )
                    current = actual
                    if deferred_selector:
                        # A new FB has no declaration to inspect. The verified
                        # first name creates AutoShop's VAR/BOOL default; probe
                        # its real selector before category/type changes. If a
                        # type is missing, retain this known partial buffer and
                        # stop; never claim no modification or repeat the add.
                        choices = adapter.selector_choices(op['name'], 'data_type', 'BOOL')
                        if any(choices.count(dtype) != 1 for dtype in requested):
                            raise BridgeError('Requested type is unavailable/ambiguous after first variable creation.')
                        observed = snapshot(adapter, target)
                        if (observed['variables'] != current or observed['source'] != before['source']
                                or observed['native_sha256'] != before['native_sha256'] or not observed['modified']):
                            raise BridgeError('First-variable selector changed the verified buffer.')
                        type_context.check(context)
                        deferred_selector = False
                    if op["category"] != "VAR":
                        desired = copy.deepcopy(current)
                        desired[-1]["category"] = op["category"]
                        actual = adapter.set_cell(
                            op["name"], "category", "VAR", op["category"]
                        )
                        if op["category"] == "INOUT":
                            # References have no editable independent initializer.
                            desired[-1].update(
                                initial_raw=actual[-1]["initial_raw"],
                                initial_value=actual[-1]["initial_value"],
                            )
                        if actual != desired:
                            raise BridgeError(
                                "FB category full-table readback differs."
                            )
                        current = actual
                    if op["data_type"] != "BOOL":
                        desired = copy.deepcopy(current)
                        desired[-1]["data_type"] = op["data_type"]
                        actual = adapter.set_cell(
                            op["name"], "data_type", "BOOL", op["data_type"]
                        )
                        if (
                            op["data_type"] in ("INT", "DINT")
                            and op["category"] != "INOUT"
                        ):
                            desired[-1].update(initial_value="0", initial_raw="0")
                        else:
                            desired[-1].update(
                                initial_raw=actual[-1]["initial_raw"],
                                initial_value=actual[-1]["initial_value"],
                            )
                        if actual != desired:
                            raise BridgeError(
                                "FB integer type/default full-table readback differs."
                            )
                        current = actual
                    subops = [
                        dict(
                            name=op["name"],
                            field=f,
                            expected=current[-1][f],
                            value=op[f],
                        )
                        for f in ("initial_value", "comment")
                        if op[f] is not None and current[-1][f] != op[f]
                    ]
                else:
                    subops = [op]
                for item in subops:
                    desired = copy.deepcopy(current)
                    row = next(r for r in desired if r["name"] == item["name"])
                    row[item["field"]] = item["value"]
                    if item["field"] == "initial_value":
                        row["initial_raw"] = item["value"]
                    if desired == current:
                        continue
                    if deferred_sets:
                        write_cell(
                            item["name"], item["field"], item["expected"], item["value"]
                        )
                    else:
                        actual = adapter.set_cell(
                            item["name"], item["field"], item["expected"], item["value"]
                        )
                        if actual != desired:
                            raise BridgeError(
                                "Full variable table readback differs after edit."
                            )
                    current = desired
                if adapter.read().source.decode("utf-8") != before["source"]:
                    raise BridgeError("Variable edit unexpectedly changed body.")
                assert_hash(target, expected.lower())
                type_context.check(context)
            after = snapshot(adapter, target)
            if after["variables"] != current:
                raise BridgeError("Full variable table readback differs after edits.")
            if not after["modified"]:
                raise BridgeError("Variable readback/dirty state verification failed.")
            write_json_new(saved / "editor_expected.json", after)
            result = dict(
                status="variables_updated_not_saved",
                target=str(target),
                backup=str(saved),
                variable_count=len(current),
                opened=opened,
                requires_manual_save=True,
                autoshop_compile_verified=False,
                initialization_scope="scalar_exact; complex IDE defaults recorded as opaque, display previews may differ",
            )
            if save:
                assert_hash(target, expected.lower())
                type_context.check(context)
                adapter.save()
                new_hash = verify_saved(adapter, target, after)
                verify_native_preserved(
                    raw, target.read_bytes(), operations, context["types"], current
                )
                new_obj = parse(target.read_bytes())
                write_json_new(
                    saved / "native_added_variables.json",
                    dict(
                        schema=1,
                        variables=[
                            v.as_dict(i)
                            for i, v in enumerate(new_obj.variables)
                            if i >= len(before["variables"])
                        ],
                        initialization_scope="IDE default for complex variables; raw preview is not native equality",
                    ),
                )
                result.update(
                    status="variables_saved",
                    sha256=new_hash,
                    requires_manual_save=False,
                )
                if close_after:
                    adapter.close()
                    result["status"] = "variables_saved_closed"
            write_json_new(saved / "variable_result.json", result)
            return result
        except (OSError, BridgeError) as exc:
            raise BridgeError(
                "{} Variable buffer or saved file may have changed; inspect AutoShop. Backup: {}".format(
                    exc, saved
                )
            ) from exc
