"""Explicit dependency-ordered changes with preflight and append-only journals.

Each existing writer owns backups and conflicts. This is deliberately not an
atomic project transaction, and never attempts to discard user editor state.
"""

from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.storage import read_json, regular_file, sha256, write_json_new


def load_plan(plan_file):
    from autoshop_bridge import service
    from autoshop_bridge.workflows import tables as table_service

    plan_file = regular_file(plan_file)
    raw = plan_file.read_bytes()
    plan = read_json(plan_file)
    if (
        set(plan) != {"schema", "project", "steps"}
        or plan["schema"] != 1
        or not isinstance(plan["project"], str)
        or not Path(plan["project"]).is_absolute()
        or not isinstance(plan["steps"], list)
        or not 1 <= len(plan["steps"]) <= 100
    ):
        raise BridgeError(
            "Change plan requires schema=1, absolute project and 1..100 steps."
        )
    project = Path(plan["project"]).resolve(strict=True)
    if not project.is_dir():
        raise BridgeError("Change project must be a directory.")
    steps, ids, targets = [], set(), set()
    for item in plan["steps"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "workspace", "kind", "method", "after"}
            or not isinstance(item["id"], str)
            or not item["id"].isascii()
            or not item["id"].replace("_", "").isalnum()
            or len(item["id"]) > 50
            or item["id"] in ids
            or item["kind"] not in ("source", "table")
            or item["method"] not in ("file", "editor")
            or not isinstance(item["workspace"], str)
            or not Path(item["workspace"]).is_absolute()
            or not isinstance(item["after"], list)
            or any(not isinstance(x, str) for x in item["after"])
        ):
            raise BridgeError(
                "Invalid/duplicate change step, method or dependency list."
            )
        ws = Path(item["workspace"]).resolve(strict=True)
        if item["kind"] == "source":
            manifest, obj, source = service.load_workspace(ws)
        else:
            manifest, obj, ops, result = table_service.load(ws)
        target = Path(manifest["native_path"]).resolve(strict=True)
        if project not in target.parents or target in targets:
            raise BridgeError("Duplicate target or target outside plan project.")
        targets.add(target)
        ids.add(item["id"])
        fingerprint = workspace_fingerprint(ws, item["kind"])
        steps.append(
            dict(item, workspace=ws, target=target, workspace_fingerprint=fingerprint)
        )
    ordered, pending = [], list(steps)
    while pending:
        ready = [
            s
            for s in pending
            if all(dep in {o["id"] for o in ordered} for dep in s["after"])
        ]
        if not ready:
            raise BridgeError("Change dependency cycle or unknown predecessor.")
        ordered.extend(ready)
        pending = [s for s in pending if s not in ready]
    return project, ordered, sha256(raw)


def workspace_fingerprint(workspace, kind):
    names = ["manifest.json", "original.native"]
    names += ["source.st"] if kind == "source" else ["table.json", "changes.json"]
    if kind == "source" and (workspace / "variables.json").exists():
        names.append("variables.json")
    return {name: sha256(regular_file(workspace / name).read_bytes()) for name in names}


def preflight(plan_file):
    from autoshop_bridge import service
    from autoshop_bridge.workflows import tables as table_service

    project, steps, digest = load_plan(plan_file)
    checks = []
    for step in steps:
        check = (
            service.check(step["workspace"], method=step["method"])
            if step["kind"] == "source"
            else table_service.check(step["workspace"])
        )
        checks.append(
            dict(
                id=step["id"],
                target=str(step["target"]),
                kind=step["kind"],
                method=step["method"],
                check=check,
                workspace_fingerprint=step["workspace_fingerprint"],
            )
        )
    # Two global additions exported from the same sibling baseline invalidate
    # one another. Refuse before any write; re-export after the first group.
    gvt_adds = []
    for step in steps:
        if step["kind"] == "table" and step["target"].suffix.lower() == ".gvt":
            _, _, ops, _ = table_service.load(step["workspace"])
            if any(op["op"] == "add" for op in ops):
                gvt_adds.append(step["id"])
    if gvt_adds and sum(s["target"].suffix.lower() == ".gvt" for s in steps) > 1:
        raise BridgeError(
            "GVT addition with another GVT edit needs separate re-exported groups."
        )
    if len({s["method"] for s in steps}) > 1:
        raise BridgeError(
            "Use one method per change group; mixed methods need explicit reload/re-export boundaries."
        )
    return dict(
        status="blocked"
        if any(c["check"]["status"] == "blocked" for c in checks)
        else "change_ready",
        project=str(project),
        plan_sha256=digest,
        checks=checks,
        editor_sessions_checked=False,
        project_atomic=False,
    )


def change_check(plan_file):
    return preflight(plan_file)


def change_run(plan_file, journal, experimental=False, pid=None):
    from autoshop_bridge import service
    from autoshop_bridge.workflows import tables as table_service

    if not experimental:
        raise BridgeError("Change execution requires --experimental.")
    before = preflight(plan_file)
    if before["status"] == "blocked":
        return before
    project, steps, digest = load_plan(plan_file)
    if digest != before["plan_sha256"]:
        raise BridgeError("Plan changed during preflight.")
    if [s["workspace_fingerprint"] for s in steps] != [
        c["workspace_fingerprint"] for c in before["checks"]
    ]:
        raise BridgeError("Workspace changed during preflight.")
    journal.mkdir(parents=True)  # Exclusive job, never overwrite old evidence.
    write_json_new(journal / "000_preflight.json", before)
    completed = []
    for number, step in enumerate(steps, 1):
        identity = dict(
            id=step["id"],
            target=str(step["target"]),
            kind=step["kind"],
            method=step["method"],
        )
        write_json_new(journal / ("{:03d}_started.json".format(number)), identity)
        try:
            # Re-read the plan; workspaces have their own native hash guards.
            if sha256(regular_file(plan_file).read_bytes()) != digest:
                raise BridgeError("Plan changed during execution.")
            if (
                workspace_fingerprint(step["workspace"], step["kind"])
                != step["workspace_fingerprint"]
            ):
                raise BridgeError("Workspace changed after preflight.")
            if step["method"] == "file":
                run = service.apply if step["kind"] == "source" else table_service.apply
                response = run(step["workspace"], experimental=True)
            elif step["kind"] == "source":
                _, obj, _ = service.load_workspace(step["workspace"])
                program = (
                    obj.program_name
                    if step["target"].suffix.lower() in (".fb", ".fc")
                    else step["target"].stem
                )
                response = service.editor_sync(
                    step["workspace"],
                    project,
                    program,
                    pid=pid,
                    experimental=True,
                    open_if_missing=True,
                    save=True,
                )
            else:
                response = table_service.editor_edit(
                    step["workspace"],
                    project,
                    step["target"].stem,
                    pid=pid,
                    experimental=True,
                    open_if_missing=True,
                    save=True,
                )
            write_json_new(
                journal / ("{:03d}_result.json".format(number)),
                dict(identity, result=response),
            )
            completed.append(dict(identity, result=response))
        except (BridgeError, OSError) as exc:
            result = dict(
                status="blocked",
                failed_step=step["id"],
                error=str(exc),
                completed=completed,
                remaining=[s["id"] for s in steps[number:]],
                journal=str(journal.resolve()),
                project_atomic=False,
                automatic_rollback=False,
                note="Failed step may have changed state. Inspect its backup/journal before retrying.",
            )
            write_json_new(journal / "failed.json", result)
            return result
    result = dict(
        status="changes_written",
        completed=completed,
        journal=str(journal.resolve()),
        project_atomic=False,
        requires_user_compile=True,
        file_method_requires_reload=any(s["method"] == "file" for s in steps),
    )
    write_json_new(journal / "completed.json", result)
    return result
