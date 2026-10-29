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
    cmd = commands.add_parser("structure-rename-plan", help="Plan member renames and associated metadata; source references are left to the caller")
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--changes", required=True, dest="changes_file", type=Path)
    cmd.add_argument("--workspace", required=True, type=Path)
    cmd = commands.add_parser("structure-rename-apply", help="Apply a reviewed member rename plan with full backups and readback")
    cmd.add_argument("--plan-file", required=True, type=Path)
    cmd.add_argument("--expect-plan-sha256", required=True, dest="expected_plan_sha256")
    cmd.add_argument("--backup-root", required=True, type=Path)
    cmd.add_argument("--experimental", action="store_true")
    cmd = commands.add_parser("declarations-read", help="Read declaration identities and definitions without ST source")
    cmd.add_argument("native", type=Path)
    cmd.add_argument("--output", type=Path)
    cmd = commands.add_parser("instances-editor-initial-read", help="Read actual displayed instance member initial values")
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--table", required=True)
    cmd.add_argument("--instance", required=True)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--open", dest="open_if_missing", action="store_true")
    cmd.add_argument("--output", type=Path)
    cmd = commands.add_parser("editor-declarations-delete", help="Explicit experimental declaration deletion through AutoShop")
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--object", required=True, dest="program")
    cmd.add_argument("--kind", required=True, choices=("fb", "fc", "stru", "gvt", "fbi"))
    cmd.add_argument("--changes", required=True, type=Path)
    cmd.add_argument("--expect-sha256", required=True, dest="expected_sha256")
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--open", dest="open_if_missing", action="store_true")
    cmd.add_argument("--save", action="store_true")
    cmd.add_argument("--backup-root", type=Path)
    cmd.add_argument("--experimental", action="store_true")
    cmd.add_argument("--dry-run", action="store_true")
    cmd = commands.add_parser("offline-export", help="Freeze direct-HCP project baseline into an external workspace")
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--workspace", required=True, type=Path)
    for name in ("offline-check", "offline-build"):
        cmd = commands.add_parser(name, help="Qualify existing registered offline targets" if name.endswith("check") else "Build hash-bound offline project candidates")
        cmd.add_argument("--workspace", required=True, type=Path)
        cmd.add_argument("--changes", required=True, type=Path)
    cmd = commands.add_parser("offline-apply", help="Apply an exact offline plan while holding exclusive HCP access")
    cmd.add_argument("--plan-file", required=True, type=Path)
    cmd.add_argument("--expect-plan-sha256", dest="expected_plan_sha256", required=True)
    cmd.add_argument("--backup-root", required=True, type=Path)
    cmd.add_argument("--experimental", action="store_true")
    cmd = commands.add_parser("offline-restore", help="Explicitly restore a retained offline batch after fresh backups")
    cmd.add_argument("--receipt-file", required=True, type=Path)
    cmd.add_argument("--expect-receipt-sha256", dest="expected_receipt_sha256", required=True)
    cmd.add_argument("--backup-root", required=True, type=Path)
    cmd.add_argument("--experimental", action="store_true")
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
    for name, help_text in (
        ("instances-editor-add", "Add project FB instances using IDE defaults"),
        ("instances-editor-edit", "Edit existing FBI fields with complete native readback"),
    ):
        cmd = commands.add_parser(name, help=help_text)
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
    cmd = commands.add_parser('object-plan', help='Plan normal IDE creation of a LiteST FB or structure')
    cmd.add_argument('--project', required=True, type=Path)
    cmd.add_argument('--kind', required=True, choices=('litest-fb', 'structure'))
    cmd.add_argument('--name', required=True)
    cmd.add_argument('--source-file', type=Path, help='UTF-8 initial FB body; required for litest-fb')
    cmd.add_argument('--members-file', type=Path, help='JSON list of initial BOOL/INT/DINT members; required for structure')
    cmd.add_argument('--save-project', action='store_true', help='Explicitly save project registration after this new object; rejects dirty documents')
    cmd.add_argument('--pid', type=int)
    cmd.add_argument('--output', type=Path, help='New plan JSON path outside the native project')
    cmd = commands.add_parser('object-create', help='Execute an exact clean-project object creation plan using AutoShop')
    cmd.add_argument('--plan-file', required=True, type=Path)
    cmd.add_argument('--backup-root', type=Path)
    cmd.add_argument('--experimental', action='store_true')
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
            cmd.add_argument("--registration-receipt", type=Path)
    cmd = commands.add_parser("registration-capture", help="Experimental direct-HCP receipt; target project must already be closed")
    cmd.add_argument("--project", required=True, type=Path)
    cmd.add_argument("--program", required=True)
    cmd.add_argument("--pid", type=int)
    cmd.add_argument("--output", required=True, type=Path)
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
    cmd.add_argument("--registration-receipt", type=Path)
    return root


def emit(value: dict, stream=None) -> None:
    # Escaping non-ASCII avoids failure on legacy Windows console encodings.
    print(json.dumps(value, ensure_ascii=True), file=stream or sys.stdout)


def _offline_command(command, args):
    """Developer CLI only; complete batch receipts remain in backup JSON files."""
    from autoshop_bridge.workflows import offline

    args = dict(args)
    if command in {"offline-apply", "offline-restore"}:
        if not args.pop("experimental"):
            raise BridgeError("Offline apply/restore requires --experimental and a closed target project.")
    if "changes" in args:
        args["changes_file"] = args.pop("changes")
    result = getattr(offline, command[len("offline-"):])(**args)
    summary = {key: result[key] for key in (
        "status", "workspace", "manifest", "protected_files", "registration_source",
        "excluded_nonfile_registration_count", "declared_missing_count",
        "plan", "plan_sha256", "receipt", "receipt_sha256", "backup_run", "validation", "qualification", "error", "error_code", "error_context",
        "deletion_preflight_scope", "reference_check", "compile_pending", "cascade", "instance_type_choices",
    ) if key in result}
    if isinstance(summary.get("manifest"), dict):
        del summary["manifest"]
    for key in ("written", "attempted", "backups", "targets"):
        if key in result:
            summary[key + "_count"] = len(result[key])
    return summary


def main(argv=None) -> int:
    args = vars(parser().parse_args(argv))
    command = args.pop("command")
    try:
        if command.startswith("structure-rename-"):
            from autoshop_bridge.workflows import structure_rename
            if command.endswith("apply") and not args.pop("experimental"):
                raise BridgeError("Structure rename apply requires --experimental and a closed project.")
            result = getattr(structure_rename, command[len("structure-rename-"):])(**args)
            result = {k:v for k,v in result.items() if k not in ("manifest", "before_hashes", "after_hashes", "backups")}
        elif command == "declarations-read":
            from autoshop_bridge.workflows import declarations
            result = declarations.read(**args)
            if args["output"] is not None:
                result = {key: result[key] for key in (
                    "status", "kind", "declcount", "native_sha256", "read_only")}
                result["output"] = str(args["output"].resolve())
        elif command == "editor-declarations-delete":
            from autoshop_bridge.workflows import declarations
            experimental = args.pop("experimental")
            if not args["dry_run"] and not experimental:
                raise BridgeError("Declaration deletion requires --experimental before connecting or writing.")
            declarations.validate_hash(args["expected_sha256"])
            args["document"] = declarations.read_changes(args.pop("changes"))
            if args["dry_run"]:
                args["open_if_missing"] = False
            from autoshop_bridge.windows.declaration_edit import edit
            result = edit(**args)
        elif command == "instances-editor-edit":
            from autoshop_bridge.windows.instance_edit import edit
            result = edit(**args)
        elif command == "instances-editor-initial-read":
            from autoshop_bridge.windows.instance_edit import read_initial
            result = read_initial(**args)
        elif command == "registration-capture":
            from autoshop_bridge.windows.registration_observer import capture_registration
            result = capture_registration(**args)
        else:
            result = (_offline_command(command, args) if command.startswith("offline-")
                      else getattr(service, command.replace("-", "_"))(**args))
    except (BridgeError, OSError) as exc:
        failure = {"status": "error", "error": str(exc)}
        if command.startswith("offline-"):
            from autoshop_bridge.projects.offline_guard import error_code
            failure["error_code"] = error_code(exc)
            if getattr(exc, "context", None) is not None:
                failure["error_context"] = dict(exc.context)
            if getattr(exc, "requires_close_entire_project", False):
                failure["requires_close_entire_project"] = True
        elif getattr(exc, "code", None):
            failure["error_code"] = exc.code
            if getattr(exc, "context", None):
                failure["error_context"] = dict(exc.context)
        emit(failure, sys.stderr)
        return 1
    emit(result)
    if result["status"] == "partial":
        return 2
    return 1 if result["status"] in {"blocked", "stopped"} else 0
