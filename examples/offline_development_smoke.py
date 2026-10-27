"""Synthetic offline CLI smoke; no IDE, compiler, PLC or real project access."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

sys.dont_write_bytecode = True
SKILL = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in root.rglob("*") if p.is_file()}


def fixtures(project):
    sys.path.insert(0, str(SKILL / "backend"))
    from autoshop_bridge.formats import st, tables, empty_table
    string = tables.string
    project.mkdir(parents=True)

    def native(source):
        count = source.count(b"\n") + 1
        return (b"AutoShop" + b"\0" * 249 + struct.pack("<I", len(source)) + st.encode(source)
                + struct.pack("<II", 0, count)
                + b"".join(struct.pack("<IIII", i, 0, 0, 0) for i in range(count)))

    (project / "Logic.FB").write_bytes(b"AutoShop" + b"\0" * 31 + string("Logic")
        + struct.pack("<II", 256, 0) + b"\0" * 4 + native(b"// initial") + b"\0" * 4)
    (project / "TimerBlock.FB").write_bytes(b"AutoShop" + b"\0" * 51 + string("TimerBlock")
        + struct.pack("<II", 256, 0) + b"\0" * 4 + native(b"// synthetic timer") + b"\0" * 4)
    (project / "MAIN.ST").write_bytes(native(b"// initial"))
    for name in ("InputData", "OutputData"):
        rows = b"".join(string("") + struct.pack("<I", code) + string(member) + string(comment)
                        for code, member, comment in ((1, "enabled", "Enable"),
                            (4, "command", "Command"), (16, "value", "Value")))
        (project / (name + ".stru")).write_bytes(b"AutoShop" + b"\0" * 40 + string(name)
            + struct.pack("<II", 64, 3) + rows)
    (project / "Globals.gvt").write_bytes(b"AutoShop" + b"\0" * 40 + struct.pack("<I", 1)
        + struct.pack("<II", 4, 4) + string("oldValue") + string("0")
        + struct.pack("<II", 257, 123456) + string("old declaration")
        + b"\xff\xfe\xff\0" + struct.pack("<II", 0, 0))
    fc_records = b"".join(string("") + struct.pack("<I", 1) + string(name)
        + string("Synthetic local") + struct.pack("<III", 0, 0xffffffff, 0)
        for name in ("firstLocal", "secondLocal"))
    (project / "Calc.FC").write_bytes(b"AutoShop" + b"\0" * 24 + string("Calc")
        + struct.pack("<II", 512, 2) + fc_records + b"\0" * 4 + native(b"// synthetic function"))
    (project / "EmptyCalc.FC").write_bytes(b"AutoShop" + b"\0" * 24 + string("EmptyCalc")
        + struct.pack("<II", 512, 0) + b"\0" * 4 + native(b"// synthetic empty function"))
    instance_records = b"".join(struct.pack("<II", 256, 256) + string(name) + string("")
        + struct.pack("<II", 257, 0x2100000 + index * 16) + string("Synthetic instance")
        + b"\xff\xfe\xff\0" + struct.pack("<II", 0, 0) + string("Logic") + b"\xff" * 8
        for index, name in enumerate(("firstInstance", "secondInstance")))
    header = b"AutoShop-synthetic"
    empty = header + empty_table.DECLARATION_TAIL + header + empty_table.IMPLICIT_TAIL
    offset, end = empty_table.instance_segment(empty)
    (project / "Instances.fbi").write_bytes(empty[:offset] + struct.pack("<I", 2)
        + instance_records + empty[end:])
    names = ("Logic.FB", "TimerBlock.FB", "MAIN.ST", "InputData.stru", "OutputData.stru", "Globals.gvt",
             "Calc.FC", "EmptyCalc.FC", "Instances.fbi")
    xml = "<project>" + "".join('<file id="{}"><Caption>{}</Caption><FileName>{}</FileName></file>'.format(
        i, Path(name).stem, name) for i, name in enumerate(names)) + "</project>"
    (project / "demo.hcp").write_bytes(st.encode(xml.encode("utf-16")))
    (project / "untouched.txt").write_text("Synthetic non-target", encoding="utf-8")


def run(output):
    if not output.is_absolute():
        raise ValueError("Output must be absolute")
    output = output.resolve()
    if output == SKILL or SKILL in output.parents:
        raise ValueError("Output must be outside the skill installation")
    output.mkdir(parents=True)
    started = time.perf_counter()
    before_bundle = tree(SKILL)
    report = dict(schema=1, kind="synthetic_offline_development_only", cases=[], commands=[],
                  tokens=dict(input=None, output=None, cached=None, reason="not exposed by local CLI"),
                  autoshop_opened=False, compiled=False, user_inputs_required=[])
    relocated = output / "relocated bundle" / "autoshop-bridge"
    unrelated = output / "unrelated cwd"
    unrelated.mkdir()

    def cli(skill, *args, expected=0):
        command = [sys.executable, "-B", str(skill / "backend/autoshop_bridge_cli.py"), *map(str, args)]
        t = time.perf_counter()
        res = subprocess.run(command, cwd=unrelated, capture_output=True, timeout=60)
        # Offline stopped/partial results are structured stdout even when the
        # exit status is nonzero; raised CLI errors use stderr instead.
        raw = res.stdout or res.stderr
        try:
            doc = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise AssertionError("CLI JSON missing: " + raw.decode("utf-8", errors="replace")[:2000])
        report["commands"].append(dict(arguments=list(map(str, args)), executable=command[2],
            returncode=res.returncode, status=doc.get("status"), elapsed_seconds=round(time.perf_counter()-t, 6)))
        if res.returncode != expected:
            raise AssertionError(dict(command=args, result=doc, expected_returncode=expected))
        return doc

    try:
        if sys.platform != "win32":
            report.update(status="skipped", reason="Windows share-none HCP guard unavailable; writes not simulated")
        else:
            shutil.copytree(SKILL, relocated)
            for label, location in (("A", "project-a"), ("B", "another location/示例 B")):
                start = time.perf_counter()
                skill = SKILL if label == "A" else relocated
                project, work = output / location, output / ("work-" + label)
                fixtures(project)
                from autoshop_bridge.formats import fb, fc, st, tables, instances
                baseline = tree(project)
                old_fc = fc.parse((project / "Calc.FC").read_bytes())
                old_global = tables.parse((project / "Globals.gvt").read_bytes(), "gvt")
                original_fbi = (project / "Instances.fbi").read_bytes()
                old_instances = instances.parse(original_fbi)
                old_row = old_global.rows[0]
                source = output / ("source-" + label + ".st")
                source.write_bytes(b"// synthetic added line\n// synthetic second line\n")
                declarations = [dict(op="add", name=name, data_type=dtype, category=category,
                    comment="Synthetic declaration", initial_value=value) for name, dtype, category, value in (
                        ("enabled", "BOOL", "VAR", "OFF"), ("command", "INT", "VAR", "0"),
                        ("value", "DINT", "VAR", "0"), ("request", "InputData", "INOUT", None),
                        ("response", "OutputData", "INOUT", None),
                        ("timerFirst", "TimerBlock", "VAR", None),
                        ("timerSecond", "TimerBlock", "VAR", None))]
                changes = output / ("changes-" + label + ".json")
                changes.write_text(json.dumps(dict(schema=1, targets=[
                    dict(file="Logic.FB", source_file=source.name, variable_operations=declarations),
                    dict(file="MAIN.ST", source_file=source.name),
                    dict(file="Calc.FC", variable_operations=[dict(op="add", name="refValue",
                        data_type="DINT", category="INOUT", initial_value=None, comment="Synthetic reference")]),
                    dict(file="EmptyCalc.FC", variable_operations=[dict(op="add", name=name,
                        data_type=dtype, category=category, initial_value=None, comment="Synthetic FC")
                        for name, dtype, category in (("enabled", "BOOL", "VAR"), ("inputValue", "INT", "IN"))]),
                    dict(file="Instances.fbi", variable_operations=[dict(op="add", name=name,
                        data_type="TimerBlock", initial_value=None, comment="Synthetic global FB")
                        for name in ("globalTimerA", "globalTimerB")]),
                    dict(file="Globals.gvt", variable_operations=[dict(op="add", name=name,
                        data_type=dtype, comment="Synthetic global", initial_value=None)
                        for name, dtype in (("gRequest", "InputData"), ("gResponse", "OutputData"))])])), encoding="utf-8")
                assert cli(skill, "offline-export", "--project", project, "--workspace", work)["status"] == "exported"
                assert cli(skill, "offline-check", "--workspace", work, "--changes", changes)["status"] == "checked"
                built = cli(skill, "offline-build", "--workspace", work, "--changes", changes)
                plan = Path(built["plan"])
                assert built["status"] == "built" and built["plan_sha256"] == digest(plan)
                assert tree(project) == baseline
                applied = cli(skill, "offline-apply", "--plan-file", plan, "--expect-plan-sha256", digest(plan),
                              "--backup-root", output / ("backups-" + label), "--experimental")
                assert applied["status"] == "applied"
                block = fb.parse((project / "Logic.FB").read_bytes())
                assert len(block.variables) == 7 and block.source == source.read_bytes()
                assert [row.fields[0] for row in block.variables] == [0, 0, 0, 3, 3, 0, 0]
                assert all(row.type_code == 256 and row.type_text == "TIMERBLOCK"
                    and row.initial_raw == "" and row.fields == (0, 1, 0xffffffff, 0)
                    for row in block.variables[-2:])
                assert block.line_count == 3 and block.line_table_count == 1
                assert st.parse((project / "MAIN.ST").read_bytes()).source == source.read_bytes()
                current = tables.parse((project / "Globals.gvt").read_bytes(), "gvt")
                assert len(current.rows) == 3
                first = current.rows[0]
                assert current.raw[first.start:first.end] == old_global.raw[old_row.start:old_row.end]
                for row in current.rows[1:]:
                    assert row.type_code == 64 and row.initial_raw == ""
                    assert row.metadata["address_raw"] == 0xFFFFFFFF
                full_fc = fc.parse((project / "Calc.FC").read_bytes())
                empty_fc = fc.parse((project / "EmptyCalc.FC").read_bytes())
                assert len(full_fc.variables) == 3 and len(empty_fc.variables) == 2
                assert full_fc.variables[-1].fields == (3, 0xffffffff, 0)
                assert full_fc.raw[full_fc.inner_offset - 4:] == old_fc.raw[old_fc.inner_offset - 4:]
                for old, new in zip(old_fc.variables, full_fc.variables):
                    assert old_fc.raw[old.offset:old.end] == full_fc.raw[new.offset:new.end]
                new_fbi = (project / "Instances.fbi").read_bytes()
                new_instances = instances.parse(new_fbi)
                assert new_instances["instance_count"] == 4
                for old, new in zip(old_instances["instances"], new_instances["instances"]):
                    a, b = old["record_offset"], new["record_offset"]
                    assert original_fbi[a:a+old["record_bytes"]] == new_fbi[b:b+new["record_bytes"]]
                for row in new_instances["instances"][2:]:
                    assert row["data_type"] == "TimerBlock" and row["initial_value_raw"] == ""
                    assert row["uninterpreted_metadata"]["flags_raw"] == 0
                    assert row["uninterpreted_metadata"]["address_raw"] == 0xffffffff
                for name in set(baseline) - {"Logic.FB", "MAIN.ST", "Globals.gvt", "Calc.FC", "EmptyCalc.FC", "Instances.fbi"}:
                    assert digest(project / name) == baseline[name], name
                before_fields = tree(project)
                field_changes = output / ("fbi-fields-" + label + ".json")
                field_changes.write_text(json.dumps(dict(schema=1, targets=[dict(file="Instances.fbi", variable_operations=[
                    dict(op="set", name="firstInstance", field="name", expected="firstInstance", value="editedInstance"),
                    dict(op="set", name="editedInstance", field="comment", expected="Synthetic instance", value="Edited instance"),
                    dict(op="set", name="editedInstance", field="initial_value", expected="", value="(enabled:=ON)"),
                ])])), encoding="utf-8")
                field_work = output / ("fbi-fields-work-" + label)
                cli(skill, "offline-export", "--project", project, "--workspace", field_work)
                cli(skill, "offline-check", "--workspace", field_work, "--changes", field_changes)
                field_plan = cli(skill, "offline-build", "--workspace", field_work, "--changes", field_changes)
                field_result = cli(skill, "offline-apply", "--plan-file", field_plan["plan"],
                    "--expect-plan-sha256", field_plan["plan_sha256"], "--experimental",
                    "--backup-root", output / ("fbi-fields-backups-" + label))
                assert field_result["status"] == "applied"
                edited_raw = (project / "Instances.fbi").read_bytes()
                edited = instances.parse(edited_raw)
                assert edited["instance_count"] == new_instances["instance_count"]
                assert (edited["instances"][0]["name"], edited["instances"][0]["comment"],
                    edited["instances"][0]["initial_value_raw"]) == ("editedInstance", "Edited instance", "(enabled:=ON)")
                assert edited["instances"][0]["uninterpreted_metadata"] == new_instances["instances"][0]["uninterpreted_metadata"]
                assert edited["opaque_prefix_sha256"] == new_instances["opaque_prefix_sha256"]
                assert edited["opaque_suffix_sha256"] == new_instances["opaque_suffix_sha256"]
                for old, new in zip(new_instances["instances"][1:], edited["instances"][1:]):
                    a, b = old["record_offset"], new["record_offset"]
                    assert new_fbi[a:a+old["record_bytes"]] == edited_raw[b:b+new["record_bytes"]]
                assert all(digest(project / name) == value for name, value in before_fields.items() if name != "Instances.fbi")
                cli(skill, "offline-restore", "--receipt-file", field_result["receipt"],
                    "--expect-receipt-sha256", field_result["receipt_sha256"], "--experimental",
                    "--backup-root", output / ("fbi-fields-restore-" + label))
                assert tree(project) == before_fields
                # Exercise the new declaration API through the exported CLI,
                # then restore the entire deletion stage before the outer restore.
                before_delete = tree(project)
                delete_targets = []
                counts = {}
                for filename, member in (("Logic.FB", "enabled"), ("Calc.FC", "firstLocal"),
                        ("InputData.stru", "command"), ("Globals.gvt", "gRequest"),
                        ("Instances.fbi", "firstInstance")):
                    snapshot = cli(skill, "declarations-read", project / filename)
                    assert snapshot["read_only"] and not snapshot["authorizes_write"]
                    row = next(v for v in snapshot["declarations"] if v["name"] == member)
                    counts[filename] = snapshot["declcount"] - 1
                    delete_targets.append(dict(file=filename, variable_operations=[dict(op="delete",
                        name=member, expected_record_sha256=row["record_sha256"])]))
                delete_changes = output / ("delete-" + label + ".json")
                delete_changes.write_text(json.dumps(dict(schema=1, targets=delete_targets)), encoding="utf-8")
                delete_work = output / ("delete-work-" + label)
                cli(skill, "offline-export", "--project", project, "--workspace", delete_work)
                checked = cli(skill, "offline-check", "--workspace", delete_work, "--changes", delete_changes)
                assert checked["reference_check"] == "not_performed_by_design" and not checked["cascade"]
                deletion = cli(skill, "offline-build", "--workspace", delete_work, "--changes", delete_changes)
                deleted = cli(skill, "offline-apply", "--plan-file", deletion["plan"],
                    "--expect-plan-sha256", deletion["plan_sha256"], "--experimental",
                    "--backup-root", output / ("delete-backups-" + label))
                assert deleted["status"] == "applied"
                after_delete = tree(project)
                for filename, count in counts.items():
                    assert cli(skill, "declarations-read", project / filename)["declcount"] == count
                for filename in set(before_delete) - set(counts):
                    assert after_delete[filename] == before_delete[filename], filename
                cli(skill, "offline-apply", "--plan-file", deletion["plan"],
                    "--expect-plan-sha256", deletion["plan_sha256"], "--experimental",
                    "--backup-root", output / ("stale-backups-" + label), expected=1)
                assert tree(project) == after_delete
                cli(skill, "offline-restore", "--receipt-file", deleted["receipt"],
                    "--expect-receipt-sha256", deleted["receipt_sha256"], "--experimental",
                    "--backup-root", output / ("delete-restore-" + label))
                assert tree(project) == before_delete
                receipt = Path(applied["receipt"])
                assert applied["receipt_sha256"] == digest(receipt)
                restored = cli(skill, "offline-restore", "--receipt-file", receipt,
                    "--expect-receipt-sha256", digest(receipt), "--backup-root", output / ("restore-" + label), "--experimental")
                assert restored["status"] == "applied" and tree(project) == baseline
                report["cases"].append(dict(case=label, status="passed", project=str(project),
                    fb_seven_variables=True, fb_internal_project_instances=True, fbi_unallocated_project_instances=True,
                    fbi_existing_name_comment_initial_fields=True,
                    gvt_unallocated_structures=True, source_lines_added=True,
                    fc_nonempty_and_empty_additions=True,
                    declaration_delete_five_kinds=True, stale_delete_replay_refused=True,
                    old_records_preserved=True, non_targets_preserved=True, restored_all_bytes=True,
                    elapsed_seconds=round(time.perf_counter()-start, 6)))
            assert tree(SKILL) == before_bundle and tree(relocated) == before_bundle
            report.update(status="passed", bundle_unchanged=True, relocated_bundle_unchanged=True)
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        report["elapsed_seconds"] = round(time.perf_counter()-started, 6)
        (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(status=report["status"], report=str(output / "results.json"),
                elapsed_seconds=report["elapsed_seconds"], cases=len(report["cases"]), compiled=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(run(parser.parse_args().output)))
