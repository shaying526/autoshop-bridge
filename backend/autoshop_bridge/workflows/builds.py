"""Import compiler text evidence without triggering compilation or inventing freshness."""

import re
from pathlib import Path, PurePosixPath

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.projects.inventory import scan
from autoshop_bridge.workflows.source import bounded_int, clipped
from autoshop_bridge.storage import (
    read_json,
    regular_file,
    sha256,
    utc_now,
    write_json_new,
)

DIAGNOSTIC = re.compile(
    r"^\s*(?P<file>.+?\.(?:ST|FB|FC|LD))\s*\(\s*(?P<line>\d+)"
    r"(?:\s*,\s*(?P<column>\d+))?\s*\)\s*:?\s*"
    r"(?P<severity>error|warning|错误|警告)\s*:?\s*(?P<message>.*)$",
    re.I,
)

# This is a user's transcription format, not a verified AutoShop output grammar.
MANUAL_LOCATION = re.compile(
    r"^\s*(?:编译)?(?:报错|错误)\s+(?P<program>[^\W\d]\w*)\s+"
    r"行号\s*[:：]?\s*(?P<line>[1-9]\d{0,8})\s*[,，:：]\s*(?P<message>\S.*)\s*$"
)


def snapshot_project(project):
    inventory = scan(project)
    files = [
        dict(file=f["file"], sha256=f.get("sha256"))
        for f in inventory["files"]
        if f.get("kind")
        in (
            "st_program",
            "function_block",
            "structure",
            "global_variables",
            "function_pending",
            "function",
            "ladder_pending",
            "function_block_instances",
            "function_instances_pending",
        )
    ]
    return dict(
        project=inventory["project"],
        project_file=inventory["project_file"],
        registration_sha256=inventory["registration_source"]["sha256"],
        registration_possibly_stale=inventory["registration_source"]["possibly_stale"],
        files=files,
    )


def build_baseline(project, output):
    data = dict(
        schema=1,
        status="build_baseline",
        observed_at=utc_now(),
        **snapshot_project(project),
    )
    write_json_new(output, data)
    return dict(
        status="build_baseline",
        output=str(output.resolve()),
        files=len(data["files"]),
        requires_user_compile=True,
        compilation_triggered=False,
    )


def parse_diagnostics(text):
    diagnostics, unknown = [], []
    for number, line in enumerate(text.splitlines(), 1):
        match = DIAGNOSTIC.match(line)
        if match:
            data = match.groupdict()
            data.update(
                line=int(data["line"]),
                column=int(data["column"]) if data["column"] else None,
                severity="error"
                if data["severity"].casefold() in ("error", "错误")
                else "warning",
                log_line=number,
            )
            data["message"] = clipped(data["message"])
            diagnostics.append(data)
        elif MANUAL_LOCATION.match(line):
            data = MANUAL_LOCATION.match(line).groupdict()
            data.update(
                file=None,
                line=int(data["line"]),
                column=None,
                severity="error",
                log_line=number,
                location_evidence="user_reported",
                file_resolution="unresolved_program",
            )
            data["message"] = clipped(data["message"])
            diagnostics.append(data)
        elif re.search(r"error|warning|错误|警告|报错", line, re.I):
            if not re.search(
                r"\b\d+\s+errors?\b|错误\s*[:：]?\s*\d+|\b\d+\s*个?错误", line, re.I
            ):
                unknown.append(dict(log_line=number, **clipped(line)))
    # Summaries are reported text only, never independent proof of a new compile.
    zero = bool(
        re.search(
            r"\b0\s+errors?\b|(?:错误\s*[:：]?\s*0(?:\D|$))|(?:\b0\s*个?错误)",
            text,
            re.I,
        )
    )
    nonzero = bool(
        re.search(
            r"\b[1-9]\d*\s+errors?\b|错误\s*[:：]?\s*[1-9]\d*|\b[1-9]\d*\s*个?错误",
            text,
            re.I,
        )
    )
    failed = any(d["severity"] == "error" for d in diagnostics) or nonzero
    unknown_errors = any(
        re.search(r"error|错误|报错", u["text"], re.I) for u in unknown
    )
    outcome = (
        "reported_fail"
        if failed
        else "reported_pass"
        if zero and not unknown_errors
        else "unknown"
    )
    return dict(
        diagnostics=diagnostics,
        unparsed_diagnostic_lines=unknown,
        reported_outcome=outcome,
    )


def resolve_program_locations(diagnostics, files):
    """Resolve extension-free manual program names only against unique registration."""
    for diagnostic in diagnostics:
        if diagnostic.get("location_evidence") != "user_reported":
            continue
        matches = [
            row["file"]
            for row in files
            if PurePosixPath(row["file"].replace("\\", "/")).suffix.casefold()
            in (".st", ".fb", ".fc", ".ld")
            and PurePosixPath(row["file"].replace("\\", "/")).stem.casefold()
            == diagnostic["program"].casefold()
        ]
        if len(matches) == 1:
            diagnostic.update(file=matches[0], file_resolution="unique_registered_name")
        elif matches:
            diagnostic.update(file_resolution="ambiguous_registered_name")


def build_report(
    project, log_file, baseline_file=None, encoding="utf-8", output=None, limit=20
):
    bounded_int(limit, 1, 100, "limit")
    if encoding not in ("utf-8", "utf-8-sig", "gbk", "utf-16"):
        raise BridgeError("Unsupported explicit log encoding.")
    path = regular_file(log_file)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise BridgeError(
            "Build log exceeds 4 MiB; provide the relevant compiler output."
        )
    raw = path.read_bytes()
    try:
        text = raw.decode(encoding)
    except UnicodeError as exc:
        raise BridgeError(
            "Build log encoding mismatch; specify its actual encoding."
        ) from exc
    current = snapshot_project(project)
    baseline_matches = None
    if baseline_file:
        baseline = read_json(regular_file(baseline_file))
        if baseline.get("schema") != 1 or baseline.get("status") != "build_baseline":
            raise BridgeError("Invalid build baseline file.")
        baseline_matches = all(
            baseline.get(key) == value for key, value in current.items()
        )
        if not baseline_matches:
            raise BridgeError(
                "Project changed since build baseline; compile the new state."
            )
    parsed = parse_diagnostics(text)
    resolve_program_locations(parsed["diagnostics"], current["files"])
    result = dict(
        status="build_report",
        schema=1,
        **current,
        **parsed,
        observed_at=utc_now(),
        log_file=str(path),
        log_sha256=sha256(raw),
        baseline_matches=baseline_matches,
        compile_freshness="unverified",
        autoshop_compile_verified=False,
        compilation_triggered=False,
        note="Imported text is evidence only. UI run identity/freshness is not proven.",
    )
    if output:
        write_json_new(output, result)
    return dict(
        status="build_report",
        project=current["project"],
        log_sha256=sha256(raw),
        reported_outcome=parsed["reported_outcome"],
        baseline_matches=baseline_matches,
        compile_freshness="unverified",
        autoshop_compile_verified=False,
        total_diagnostics=len(parsed["diagnostics"]),
        diagnostics=parsed["diagnostics"][:limit],
        unparsed_count=len(parsed["unparsed_diagnostic_lines"]),
        unparsed_diagnostic_lines=parsed["unparsed_diagnostic_lines"][:limit],
        truncated=len(parsed["diagnostics"]) > limit
        or len(parsed["unparsed_diagnostic_lines"]) > limit,
        output=str(output.resolve()) if output else None,
    )
