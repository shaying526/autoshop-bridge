"""Synthetic-only CLI acceptance; never discovers or opens a real IDE/project.

Fixture construction uses the packaged encoder; all processing uses the public CLI.
No customer fixtures, compiler logs, credentials or global settings are required.
"""

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


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(root):
    return {p.relative_to(root).as_posix(): hash_file(p) for p in root.rglob("*") if p.is_file()}


def fixtures(output):
    # Fixture generation is not an additional native-file editing API.
    sys.path.insert(0, str(SKILL / "backend"))
    from autoshop_bridge.formats.st import encode

    def text(value):
        raw = value.encode("utf-8")
        return bytes([len(raw)]) + raw

    def st(source):
        count = source.count(b"\n") + 1
        return (b"AutoShop" + b"\0" * 249 + struct.pack("<I", len(source)) + encode(source)
                + struct.pack("<II", 0, count)
                + b"".join(struct.pack("<IIII", i, 0, 0, 0) for i in range(count)))

    result = []
    for case, directory, name in [("A", "project-a", "SBR_Example.ST"),
                                  ("B", "another location/示例 B", "CalcDemo.FC")]:
        project = output / directory
        project.mkdir(parents=True)
        source = b"// Example original\n"
        raw = st(source)
        if case == "B":
            record = (text("") + struct.pack("<I", 1) + text("ready") + text("Synthetic local")
                      + struct.pack("<III", 0, 0xffffffff, 0))
            raw = (b"AutoShop" + b"\0" * 24 + text("CalcDemo") + struct.pack("<II", 512, 1)
                   + record + b"\0" * 4 + raw)
        target = project / name
        target.write_bytes(raw)
        xml = ('<project><file id="1"><Caption>{0}</Caption><FileName>{1}</FileName>'
               '</file></project>').format(target.stem, name)
        (project / "demo.hcp").write_bytes(encode(xml.encode("utf-16")))
        (project / "untouched.txt").write_text("Synthetic non-target sentinel", encoding="utf-8")
        result.append((case, project, target))
    return result


def run(output):
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("Output must be absolute")
    # Resolve existing ancestors before containment checks; never put test writes
    # in a Skill installation, even through a directory link.
    output = output.resolve()
    if output == SKILL or SKILL in output.parents:
        raise ValueError("Output must be outside the skill installation")
    output.mkdir(parents=True)  # Exclusive: never reuse a real/existing directory.
    started = time.perf_counter()
    before_bundle = tree(SKILL)
    relocated = output / "relocated skill" / "autoshop-bridge"
    shutil.copytree(SKILL, relocated)
    unrelated = output / "unrelated cwd"
    unrelated.mkdir()
    commands, cases = [], []
    report = dict(schema=1, kind="synthetic_offline_only", cases=cases, commands=commands,
                  tokens=dict(input=None, output=None, cached=None, reason="not exposed by local CLI"),
                  user_inputs_required=[], autoshop_opened=False, compiled=False)

    def cli(skill, *args, expected=0):
        command = [sys.executable, "-B", str(skill / "backend/autoshop_bridge_cli.py"), *map(str, args)]
        t = time.perf_counter()
        res = subprocess.run(command, cwd=unrelated, capture_output=True, timeout=45)
        raw = res.stdout if res.returncode == 0 else res.stderr
        try:
            doc = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise AssertionError("CLI did not produce JSON: " + raw.decode("utf-8", errors="replace")[:2000])
        commands.append(dict(arguments=list(map(str, args)), executable=str(skill / "backend/autoshop_bridge_cli.py"),
                             returncode=res.returncode, status=doc.get("status"),
                             elapsed_seconds=round(time.perf_counter()-t, 6)))
        if res.returncode != expected:
            raise AssertionError(dict(command=args, result=doc, expected_returncode=expected))
        return doc

    try:
        for label, project, target in fixtures(output):
            start = time.perf_counter()
            skill = SKILL if label == "A" else relocated
            original = target.read_bytes()
            baseline = tree(project)
            work = output / ("work-" + label)
            cli(skill, "project-summary", "--project", project, "--limit", 5)
            exported = cli(skill, "export", target, "--workspace", work)
            variables = (work / "variables.json").read_bytes() if label == "B" else None
            read = cli(skill, "source-read", work, "--start", 1, "--limit", 20)
            patch = output / ("patch-" + label + ".json")
            patch.write_text(json.dumps(dict(schema=1, source_sha256=read["source_sha256"],
                                            operations=[dict(old="// Example original", new="// Example revised")])), encoding="utf-8")
            cli(skill, "source-patch", work, "--patch-file", patch, "--dry-run")
            cli(skill, "source-patch", work, "--patch-file", patch)
            stale = cli(skill, "source-patch", work, "--patch-file", patch, expected=1)
            assert stale["status"] == "error"
            ready = cli(skill, "check", work, "--method", "file")
            assert ready["status"] == "ready"
            candidate = output / ("candidate-" + label + target.suffix)
            cli(skill, "build", work, "--output", candidate, "--experimental")
            applied = cli(skill, "apply", work, "--experimental")
            assert applied["status"] == "replaced" and target.read_bytes() == candidate.read_bytes()
            backup = Path(applied["backup"])
            assert (backup / "original.native").read_bytes() == original
            after_work = output / ("after-" + label)
            after_export = cli(skill, "export", target, "--workspace", after_work)
            assert (after_work / "source.st").read_bytes() == b"// Example revised\n"
            if variables is not None:
                assert (after_work / "variables.json").read_bytes() == variables
            # The 32-bit payload length is allowed to change; opaque envelope
            # bytes, variable records and complete line metadata must not.
            offset = exported["payload_offset"]
            payload_size = exported["source_bytes"]
            changed = target.read_bytes()
            assert changed[:offset-4] == original[:offset-4]
            assert changed[offset+after_export["source_bytes"]:] == original[offset+payload_size:]
            blocked = cli(skill, "apply", work, "--experimental", expected=1)
            assert blocked["status"] in ("error", "blocked")
            cli(skill, "restore", backup, "--expect-sha256", hash_file(target))
            assert target.read_bytes() == original
            for name, digest in baseline.items():
                assert hash_file(project / name) == digest, name
            cases.append(dict(case=label, project=str(project), target=str(target), status="passed",
                              elapsed_seconds=round(time.perf_counter()-start, 6),
                              variables_preserved=label == "B", backup_verified=True,
                              non_target_preserved=True, original_restored=True,
                              stale_patch_and_external_conflict_rejected=True))
        assert tree(SKILL) == before_bundle
        assert tree(relocated) == before_bundle
        report.update(status="passed", bundle_unchanged=True, relocated_bundle_unchanged=True)
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        report["elapsed_seconds"] = round(time.perf_counter()-started, 6)
        (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(status=report["status"], report=str(output / "results.json"),
                elapsed_seconds=report["elapsed_seconds"], cases=len(cases), compiled=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output)))
