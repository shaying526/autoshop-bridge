"""JSON command-line interface; errors go to stderr with a nonzero status."""

import argparse
import json
import sys
from pathlib import Path

from autoshop_bridge import __version__
from autoshop_bridge import service
from autoshop_bridge.errors import BridgeError


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="autoshop_bridge",
        description="AutoShop ST / ST-backed FB / FC source bridge (experimental write-back).",
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("system-variables-read", help="Read vendor system definitions for registered system tables")
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--definitions-dir", required=True, type=Path)
    cmd.add_argument("--table")
    cmd.add_argument("--type-name")
    cmd.add_argument("--search")
    cmd.add_argument("--limit", type=int, default=20)
    cmd.add_argument("--offset", type=int, default=0)
    cmd.add_argument("--output", type=Path)
    cmd = commands.add_parser(
        "instances-editor-read", help="Read the global FB instance editor"
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--table", required=True)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--open", dest="open_if_missing", action="store_true")
    cmd.add_argument("--output", type=Path)
    cmd = commands.add_parser(
        "instances-editor-add", help="Add project FB instances using IDE defaults"
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--table", required=True)
    cmd.add_argument("--changes", required=True, type=Path)
    cmd.add_argument("--expect-sha256", dest="expected", required=True)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--open", dest="open_if_missing", action="store_true")
    cmd.add_argument("--save", action="store_true")
    cmd.add_argument("--close", dest="close_after", action="store_true")
    cmd.add_argument("--experimental", action="store_true")
    cmd.add_argument("--dry-run", action="store_true")
    cmd.add_argument("--backup-root", type=Path)
    cmd = commands.add_parser(
        "object-dialog", help="Inspect the already-open normal new-program dialog"
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--pid", type=int)
    cmd = commands.add_parser(
        "object-create-st",
        help="Create and initialize LiteST from an already-open dialog",
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument(
        "--name", required=True, help="Dialog suffix; observed AutoShop adds SBR_"
    )
    cmd.add_argument("--source-file", required=True, type=Path)
    cmd.add_argument("--expect-dialog-sha256", dest="expected_dialog_sha256")
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--backup-root", type=Path)
    cmd.add_argument("--experimental", action="store_true")
    cmd.add_argument("--dry-run", action="store_true")
    cmd = commands.add_parser(
        "build-baseline",
        help="Capture project hashes before user-triggered compilation",
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--output", required=True, type=Path)
    cmd = commands.add_parser(
        "build-report",
        help="Import diagnostic text; does not trigger or certify compilation",
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--log-file", required=True, type=Path)
    cmd.add_argument("--baseline-file", type=Path)
    cmd.add_argument(
        "--encoding", choices=("utf-8", "utf-8-sig", "gbk", "utf-16"), default="utf-8"
    )
    cmd.add_argument("--output", type=Path)
    cmd.add_argument("--limit", type=int, default=20)
    cmd = commands.add_parser(
        "change-check", help="Preflight dependency-ordered source/table workspaces"
    )
    cmd.add_argument("--plan-file", required=True, type=Path)
    cmd = commands.add_parser(
        "change-run", help="Execute an explicit change group with backups and a journal"
    )
    cmd.add_argument("--plan-file", required=True, type=Path)
    cmd.add_argument("--journal", required=True, type=Path)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--experimental", action="store_true")
    cmd = commands.add_parser(
        "source-read",
        help="Read bounded lines or literal matches from a source workspace",
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--start", type=int, default=1)
    cmd.add_argument("--end", type=int)
    cmd.add_argument("--search")
    cmd.add_argument("--context", type=int, default=2)
    cmd.add_argument("--limit", type=int, default=20)
    cmd.add_argument("--expect-sha256", dest="expected")
    cmd = commands.add_parser(
        "source-patch",
        help="Apply a hash-bound local source patch; native/editor unchanged",
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--patch-file", required=True, type=Path)
    cmd.add_argument("--dry-run", action="store_true")
    cmd = commands.add_parser(
        "source-restore", help="Restore local source patch history with a safety backup"
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--saved", required=True, type=Path)
    cmd.add_argument("--expect-sha256", dest="expected", required=True)
    cmd = commands.add_parser(
        "code-query", help="Query disk declarations and conservative code relationships"
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--symbol", required=True)
    cmd.add_argument(
        "--relation",
        choices=(
            "definitions",
            "references",
            "type-users",
            "dependencies",
            "callers",
            "impact",
            "instances",
        ),
        default="definitions",
    )
    cmd.add_argument("--limit", type=int, default=20)
    cmd.add_argument("--offset", type=int, default=0)
    cmd = commands.add_parser(
        "code-context",
        help="Bounded AI context for definitions, instances and call candidates",
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--symbol", required=True)
    cmd.add_argument("--max-items", type=int, default=20)
    cmd = commands.add_parser(
        "table-export", help="Export native STRU/GVT to a new table workspace"
    )
    cmd.add_argument("native", type=Path)
    cmd.add_argument("--workspace", required=True, type=Path)
    cmd = commands.add_parser(
        "table-check", help="Validate table operations and native baseline"
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--target", type=Path)
    cmd = commands.add_parser(
        "table-build", help="Build a new native STRU/GVT candidate"
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--output", required=True, type=Path)
    cmd.add_argument("--experimental", action="store_true")
    cmd = commands.add_parser(
        "table-apply", help="Apply native table changes after verified backup"
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--target", type=Path)
    cmd.add_argument("--experimental", action="store_true")
    cmd.add_argument("--backup-root", type=Path)
    for name in ("table-editor-read", "table-editor-close"):
        cmd = commands.add_parser(name, help="Read or safely close a STRU/GVT editor")
        cmd.add_argument("--project", required=True, type=Path)
        cmd.add_argument("--table", required=True)
        cmd.add_argument("--pid", type=int)
        if name == "table-editor-read":
            cmd.add_argument("--open", dest="open_if_missing", action="store_true")
            cmd.add_argument("--output", type=Path)
    cmd = commands.add_parser(
        "table-editor-edit", help="Apply table workspace changes through AutoShop"
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--table", required=True)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--open", dest="open_if_missing", action="store_true")
    cmd.add_argument("--save", action="store_true")
    cmd.add_argument("--close", dest="close_after", action="store_true")
    cmd.add_argument("--experimental", action="store_true")
    cmd.add_argument("--dry-run", action="store_true")
    cmd.add_argument("--backup-root", type=Path)
    cmd = commands.add_parser(
        "project-summary",
        help="Bounded AI project inventory without full tables or sources",
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--limit", type=int, default=20)
    cmd.add_argument("--offset", type=int, default=0)
    cmd = commands.add_parser(
        "scan", help="Read-only project/program/FB variable inventory"
    )
    cmd.add_argument("project", type=Path)
    cmd.add_argument("--output", type=Path)
    for name in ("editor-open", "editor-read", "editor-close"):
        cmd = commands.add_parser(
            name, help="Explicit Windows document " + name.split("-")[1]
        )
        cmd.add_argument("--project", required=True, type=Path)
        cmd.add_argument("--program", required=True)
        cmd.add_argument("--pid", type=int)
        if name == "editor-read":
            cmd.add_argument("--open", dest="open_if_missing", action="store_true")
            cmd.add_argument("--output", type=Path)
    cmd = commands.add_parser(
        "editor-save", help="Save exact captured editor snapshot, with backup/readback"
    )
    cmd.add_argument("snapshot_file", type=Path)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--close", dest="close_after", action="store_true")
    cmd.add_argument("--backup-root", type=Path)
    cmd = commands.add_parser(
        "editor-variables",
        help="Explicit FB variable changes through the editor (Windows)",
    )
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--program", required=True)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--changes", required=True, type=Path)
    cmd.add_argument("--expect-sha256", required=True, dest="expected")
    cmd.add_argument("--open", dest="open_if_missing", action="store_true")
    cmd.add_argument("--save", action="store_true")
    cmd.add_argument("--close", dest="close_after", action="store_true")
    cmd.add_argument("--experimental", action="store_true")
    cmd.add_argument("--dry-run", action="store_true")
    cmd.add_argument("--backup-root", type=Path)
    cmd = commands.add_parser(
        "export", help="Export native ST or supported FB/FC to a new workspace"
    )
    cmd.add_argument("native", type=Path)
    cmd.add_argument("--workspace", required=True, type=Path)
    cmd = commands.add_parser("check", help="Check workspace and target baseline")
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--target", type=Path)
    cmd.add_argument("--method", choices=("file", "editor"), default="file")
    cmd = commands.add_parser(
        "build", help="Generate a new candidate native ST/FB file"
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--output", required=True, type=Path)
    cmd.add_argument("--experimental", action="store_true")
    cmd = commands.add_parser(
        "apply", help="Replace a baseline-matching target after verified backup"
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--target", type=Path)
    cmd.add_argument("--experimental", action="store_true")
    cmd.add_argument("--backup-root", type=Path)
    cmd = commands.add_parser("backup", help="Create a unique verified backup")
    cmd.add_argument("native", type=Path)
    cmd.add_argument("--backup-root", type=Path)
    cmd = commands.add_parser(
        "restore", help="Restore a backup, first backing up current target"
    )
    cmd.add_argument("saved", type=Path)
    cmd.add_argument("--expect-sha256", required=True, dest="expected")
    cmd.add_argument("--target", type=Path)
    cmd.add_argument("--backup-root", type=Path)
    cmd = commands.add_parser(
        "editor-sync",
        help="Update one open AutoShop editor buffer; user saves afterward (Windows)",
    )
    cmd.add_argument("workspace", type=Path)
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--program", required=True)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--dry-run", action="store_true")
    cmd.add_argument("--experimental", action="store_true")
    cmd.add_argument("--backup-root", type=Path)
    cmd.add_argument("--open", dest="open_if_missing", action="store_true")
    cmd.add_argument("--save", action="store_true")
    cmd.add_argument("--close", dest="close_after", action="store_true")
    return root


def emit(value: dict, stream=None) -> None:
    # Escaping non-ASCII avoids failure on legacy Windows console encodings.
    print(json.dumps(value, ensure_ascii=True), file=stream or sys.stdout)


def main(argv=None) -> int:
    args = vars(parser().parse_args(argv))
    command = args.pop("command")
    try:
        result = getattr(service, command.replace("-", "_"))(**args)
    except (BridgeError, OSError) as exc:
        emit({"status": "error", "error": str(exc)}, sys.stderr)
        return 1
    emit(result)
    return 1 if result["status"] == "blocked" else 0
