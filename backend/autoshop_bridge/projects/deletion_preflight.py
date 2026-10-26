"""Report explicit deletion without interpreting references or type users.

The caller verifies registration, full baselines, native format, record hashes,
backups and non-target bytes. AutoShop compilation checks retained references.
"""
from pathlib import Path

from autoshop_bridge.errors import BridgeError

SCOPE = "explicit_declaration_targets_no_reference_check_v1"


def check(manifest, originals, candidates, entries):
    """Validate explicit target coverage and report the semantic-check boundary."""
    deletions = [(entry["file"], op["name"]) for entry, _ in entries
                 for op in entry.get("variable_operations", []) if op.get("op") == "delete"]
    if not deletions:
        return None
    final = dict(candidates)
    targets = [entry["file"] for entry, _ in entries]
    if len(set(targets)) != len(targets) or set(final) != set(targets):
        raise BridgeError("Deletion candidates must exactly match explicit targets.")
    for target, _ in deletions:
        if (target not in originals
                or manifest["registered"].get(target, {}).get("state") != "present"
                or Path(target).suffix.lower() not in {".fb", ".fc", ".stru", ".gvt", ".fbi"}):
            raise BridgeError("Deletion requires an existing registered declaration target.")
    return dict(scope=SCOPE, status="explicit_targets_checked",
                reference_check="not_performed_by_design", compile_pending=True,
                compiler_validation="pending", cascade=False,
                deletion_targets=sorted({target for target, _ in deletions}))
