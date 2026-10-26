"""Experimental target-only registration receipts; no mirror can issue one.

Live observations must come from a trusted adapter's current project-tree
identity observation, independently of HCPP. This module does not manufacture
that observation from document titles or cached registration. Explicit editor
read/sync routes may opt into the experimental observer; IDE validation remains
separate from these guards and their synthetic tests.
Receipts are integrity baselines, not signed credentials or a global write
permission. Default editor routes do not opt into this experimental contract.
"""

import copy
import json
from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.projects import inventory
from autoshop_bridge.storage import native_file, regular_file, sha256, utc_now, read_json

SCHEMA = "autoshop-existing-target-registration-receipt-experimental-v1"
SOURCE_SUFFIXES = {".st", ".fb", ".fc", ".ld", ".stru", ".gvt", ".fbi", ".fci", ".svt"}
TREE_KINDS = {".st": "st_program", ".fb": "function_block", ".fc": "function",
              ".ld": "ladder_program", ".stru": "structure", ".gvt": "global_variables",
              ".fbi": "function_block_instances", ".fci": "function_instances"}
LIVE_TREE_KINDS = {"st_program", "ladder_program", "function_block", "structure",
                   "global_variables", "function_block_instances"}
IDENTITY_KEYS = {"pid", "main", "exe", "creation_time"}
RECEIPT_KEYS = {"schema", "scope", "project_file", "program", "target", "target_path",
                "registration_sha256", "registration_rows", "native_hashes", "closed_identity",
                "captured_at", "source", "structural_mutation_authorized", "receipt_sha256",
                "tree_objects", "registered_file_states"}


class RegistrationEvidenceError(BridgeError):
    def __init__(self, code, message, *, context=None):
        self.code = code
        self.context = dict(context or {})
        super().__init__(code + ": " + message)


def _require(condition, code, message, context=None):
    if not condition:
        raise RegistrationEvidenceError(code, message, context=context)


def comparison(source, before, after, limit=32):
    """Bounded field differences; before is always the captured baseline.

    One level of record fields is sufficient for registration rows, process
    identity and file state/hash maps. No source text or native bytes belong here.
    """
    differences, total = [], 0
    for key in sorted(set(before) | set(after)):
        left, right = before.get(key), after.get(key)
        if key in before and key in after and left == right:
            continue
        record = left if isinstance(left, dict) else right
        name = (record.get("file") or record.get("caption") or key) if isinstance(record, dict) else key
        fields = sorted(set(left) | set(right)) if isinstance(left, dict) and isinstance(right, dict) else [None]
        for field in fields:
            a, b = (left.get(field), right.get(field)) if field is not None else (left, right)
            if field is not None and field in left and field in right and a == b:
                continue
            total += 1
            if len(differences) < limit:
                differences.append(dict(object=name, key=key, field=field or "record",
                                        before=copy.deepcopy(a), after=copy.deepcopy(b), before_present=key in before,
                                        after_present=key in after))
    return dict(evidence_source=source, comparison_against="closed_capture_receipt",
                differences=differences, difference_count=total, truncated=total > limit)


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                             allow_nan=False, separators=(",", ":")).encode("ascii"))


def _identity(value):
    _require(isinstance(value, dict) and set(value) == IDENTITY_KEYS,
             "registration_identity_mismatch", "Full process/start/window identity is required.")
    _require(all(isinstance(value[k], int) and not isinstance(value[k], bool) and value[k] > 0
                 for k in ("pid", "main", "creation_time"))
             and isinstance(value["exe"], str) and bool(value["exe"]),
             "registration_identity_mismatch", "Invalid process identity.")
    return copy.deepcopy(value)


def _observation(observed, hcp, state):
    _require(isinstance(observed, dict) and observed.get("state") == state
             and observed.get("project_file") == str(hcp) and observed.get("enabled") is True
             and observed.get("dirty") == [] and observed.get("dialogs") == []
             and observed.get("cell_edits") == [],
             "registration_needs_refresh", "A current clean {} project observation is required.".format(state),
             comparison("live_session", {"session": dict(state=state, project_file=str(hcp), enabled=True,
                        dirty=[], dialogs=[], cell_edits=[])}, {"session": {k: observed.get(k) for k in
                        ("state", "project_file", "enabled", "dirty", "dialogs", "cell_edits")}})
             if isinstance(observed, dict) else dict(evidence_source="live_session", reason="invalid_observation"))
    return _identity(observed.get("identity"))


def _rows(raw, directory):
    rows, ids, paths = [], set(), set()
    for node in inventory.registration(raw).findall("file"):
        row = dict(id=node.get("id"), caption=node.findtext("Caption") or "",
                   file=node.findtext("FileName") or "", file_type=node.findtext("FileType"),
                   program_type=node.findtext("ProgType"))
        _require(row["id"] is not None and row["id"] not in ids,
                 "registration_stale", "Registration IDs must be present and unique.")
        ids.add(row["id"])
        if row["file"]:
            path = directory.joinpath(*inventory.member_path(row["file"])).resolve()
            _require(directory in path.parents and str(path).casefold() not in paths,
                     "registration_stale", "Registration paths escape the project or are ambiguous.")
            paths.add(str(path).casefold())
        rows.append(row)
    return rows


def _target(rows, directory, program):
    matches = [row for row in rows if row["file"]
               and Path(row["file"]).suffix.lower() in (".st", ".fb", ".fc")
               and (row["caption"] == program or Path(row["file"]).stem == program)]
    _require(len(matches) == 1, "registration_identity_mismatch",
             "Exactly one registered ST/FB/FC target is required.")
    row = matches[0]
    language, _ = inventory.program_language(Path(row["file"]).suffix.lower(),
                                               row["file_type"], row["program_type"])
    _require(language != "LD", "registration_scope_denied", "Ladder targets are outside this receipt scope.")
    try:
        path = native_file(directory.joinpath(*inventory.member_path(row["file"])))
    except (OSError, BridgeError) as exc:
        raise RegistrationEvidenceError("registration_stale", "The frozen target file is unavailable: {}".format(row["file"])) from exc
    return copy.deepcopy(row), path


def _tree_objects(rows):
    """Expected named objects in all mapped project-object categories.

    The live adapter must enumerate every mapped category, including empty
    ones, and reject unknown/partial category layouts. No HCP-private ID or
    path is expected from a tree widget; those stay frozen in registration_rows.
    """
    result = [dict(caption=row["caption"], kind=TREE_KINDS[Path(row["file"]).suffix.lower()])
              for row in rows if row["file"] and Path(row["file"]).suffix.lower() in TREE_KINDS
              and TREE_KINDS[Path(row["file"]).suffix.lower()] in LIVE_TREE_KINDS]
    keys = [(item["caption"], item["kind"]) for item in result]
    _require(all(caption for caption, _ in keys) and len(keys) == len(set(keys)),
             "registration_identity_mismatch", "Tree object captions/kinds are missing or ambiguous.")
    return sorted(result, key=lambda item: (item["kind"], item["caption"]))


def _native_hashes(directory, rows):
    paths = {directory.joinpath(*inventory.member_path(row["file"])) for row in rows
             if row["file"] and Path(row["file"]).suffix.lower() in SOURCE_SUFFIXES}
    # Additional root sources are protected as well; they never become registered.
    paths.update(p for p in directory.iterdir() if p.suffix.lower() in SOURCE_SUFFIXES)
    result = {}
    for path in sorted(paths):
        try:
            checked = regular_file(path)
            _require(directory in checked.parents and checked.stat().st_nlink == 1,
                     "registration_stale", "Native dependency identity is unsafe.")
            result[checked.relative_to(directory).as_posix()] = sha256(inventory.bounded_read(checked))
        except RegistrationEvidenceError:
            raise
        except (OSError, BridgeError) as exc:
            raise RegistrationEvidenceError("registration_stale", "Native dependency cannot be verified: {}.".format(path.name),
                context=dict(evidence_source="native_files", differences=[dict(object=path.relative_to(directory).as_posix(),
                             field="readable_safe_file", before=True, after=False)], reason=str(exc))) from exc
    return result


def _registered_file_states(directory, rows):
    """Freeze every registered file, including unsupported configuration items."""
    states = {}
    for row in rows:
        if not row["file"]:
            continue
        path = directory.joinpath(*inventory.member_path(row["file"]))
        key = path.relative_to(directory).as_posix()
        if not path.exists() and not path.is_symlink():
            states[key] = dict(state="missing")
            continue
        try:
            checked = regular_file(path)
            _require(directory in checked.parents and checked.stat().st_nlink == 1,
                     "registration_stale", "Registered file identity is unsafe.")
            states[key] = dict(state="present", sha256=sha256(inventory.bounded_read(checked)))
        except RegistrationEvidenceError:
            raise
        except (OSError, BridgeError) as exc:
            raise RegistrationEvidenceError("registration_stale", "Registered file cannot be verified: {}".format(key),
                context=dict(evidence_source="registered_files", differences=[dict(object=key,
                             field="readable_safe_file", before=True, after=False)], reason=str(exc))) from exc
    return states


def capture_closed_target(project, program, closed_observation):
    """Capture direct HCP only after the caller proves the project is closed.

    Callers must obtain the observation from the actual lifecycle adapter, not
    user-edited metadata. No HCPP fallback or implicit save/close occurs here.
    """
    hcp = inventory.select_project(Path(project))
    identity = _observation(closed_observation, hcp, "closed")
    try:
        raw = inventory._read_hcp(hcp)
    except PermissionError as exc:
        raise RegistrationEvidenceError("registration_needs_refresh", "Direct HCP is unavailable; a mirror cannot issue a receipt.") from exc
    rows = _rows(raw, hcp.parent)
    target, path = _target(rows, hcp.parent, program)
    hashes = _native_hashes(hcp.parent, rows)
    file_states = _registered_file_states(hcp.parent, rows)
    _require(inventory._read_hcp(hcp) == raw and _native_hashes(hcp.parent, rows) == hashes
             and _registered_file_states(hcp.parent, rows) == file_states,
             "registration_stale", "Registration or dependencies changed during capture.")
    receipt = dict(schema=SCHEMA, scope="existing_target_content_only", project_file=str(hcp),
                   program=program, target=target, target_path=str(path),
                   registration_sha256=sha256(raw), registration_rows=rows,
                   native_hashes=hashes, closed_identity=identity, captured_at=utc_now(),
                   source="direct_closed_hcp", structural_mutation_authorized=False,
                   tree_objects=_tree_objects(rows), registered_file_states=file_states)
    receipt["receipt_sha256"] = _digest(receipt)
    return receipt


def load_receipt(value):
    """Read an explicit receipt; malformed metadata never becomes a hint."""
    if isinstance(value, dict):
        return copy.deepcopy(value)
    try:
        return read_json(Path(value))
    except (OSError, BridgeError, TypeError) as exc:
        raise RegistrationEvidenceError("registration_needs_refresh", "Receipt metadata cannot be read: {}".format(exc)) from exc


def receipt_identity(project, program, receipt, pid=None):
    """Validate receipt identity before attaching or opening any target window."""
    hcp = inventory.select_project(Path(project))
    _require(isinstance(receipt, dict) and set(receipt) == RECEIPT_KEYS,
             "registration_needs_refresh", "An explicit complete direct-HCP receipt is required.")
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    try:
        digest = _digest(body)
    except (TypeError, ValueError) as exc:
        raise RegistrationEvidenceError("registration_needs_refresh", "Receipt metadata is not canonical JSON.") from exc
    _require(receipt.get("receipt_sha256") == digest and receipt.get("schema") == SCHEMA
             and receipt.get("source") == "direct_closed_hcp"
             and receipt.get("scope") == "existing_target_content_only"
             and receipt.get("structural_mutation_authorized") is False,
             "registration_needs_refresh", "Receipt integrity or scope is invalid.")
    _require(receipt.get("project_file") == str(hcp) and receipt.get("program") == program,
             "registration_identity_mismatch", "Receipt belongs to a different project or program.",
             comparison("requested_binding", {"target": dict(project_file=receipt.get("project_file"),
                        program=receipt.get("program"))}, {"target": dict(project_file=str(hcp), program=program)}))
    identity = _identity(receipt["closed_identity"])
    _require(pid is None or pid == identity["pid"], "registration_identity_mismatch",
             "Explicit PID differs from the captured process.",
             comparison("requested_process", {"process": {"pid": identity["pid"]}}, {"process": {"pid": pid}}))
    target, path = _target(receipt["registration_rows"], hcp.parent, program)
    _require(target == receipt["target"] and str(path) == receipt["target_path"],
             "registration_identity_mismatch", "Receipt target mapping is inconsistent.")
    return dict(project_file=str(hcp), project=str(hcp.parent), target=str(path), pid=identity["pid"])


def verify_target_receipt(project, program, receipt, live_observation, *, operation="target_content"):
    """Validate one current observation; never elevate mirror hints to freshness.

    The caller must repeat this verification immediately before a write and
    discard the receipt after any structural change or process/project change.
    Native changes, including a successful content save, require a new receipt.
    """
    _require(operation in ("target_content", "target_read"), "registration_scope_denied",
             "Receipts cannot authorize creation, type additions or structural changes.")
    binding = receipt_identity(project, program, receipt)
    hcp = Path(binding["project_file"])
    identity = _observation(live_observation, hcp, "opened")
    _require(identity == receipt["closed_identity"], "registration_identity_mismatch",
             "Process/start/window identity changed since capture.",
             comparison("live_process", {"process": receipt["closed_identity"]}, {"process": identity}))
    target_kind = TREE_KINDS.get(Path(receipt["target"]["file"]).suffix.lower())
    _require(live_observation.get("target_identity_source") == "live_project_tree"
             and live_observation.get("target") == dict(caption=receipt["target"]["caption"], kind=target_kind)
             and live_observation.get("tree_inventory_complete") is True,
             "registration_needs_refresh", "Current independent complete project-tree identity is required.")
    live_objects = live_observation.get("tree_objects")
    _require(isinstance(live_objects, list) and all(isinstance(r, dict) and set(r) == {"caption", "kind"}
             and isinstance(r["caption"], str) and isinstance(r["kind"], str) for r in live_objects),
             "registration_needs_refresh", "The live project-object list is invalid.",
             dict(evidence_source="live_project_tree", reason="invalid_object_list"))
    _require(live_objects == receipt["tree_objects"],
             "registration_stale", "The live project-object tree changed or its enumeration is incomplete.",
             comparison("live_project_tree", {r["kind"] + "/" + r["caption"]: r for r in receipt["tree_objects"]},
                        {r["kind"] + "/" + r["caption"]: r for r in live_objects}))
    rows = receipt["registration_rows"]
    hint = None
    try:
        raw = inventory._read_hcp(hcp)
        hint_source = "hcp"
    except PermissionError as unavailable:
        try:
            members, validation = inventory.unpack_mirror_evidence(inventory.bounded_read(hcp.with_suffix(".hcpp")))
        except (OSError, BridgeError) as exc:
            raise RegistrationEvidenceError("registration_needs_refresh", "A bounded registration hint is unavailable: {}".format(exc),
                context=dict(evidence_source="hcpp_hint_only", reason="unavailable_or_invalid",
                             hcp_error=str(unavailable), hint_error=str(exc))) from exc
        matches = [value for name, value in members.items() if name.casefold() == hcp.name.casefold()]
        _require(len(matches) == 1, "registration_stale", "Mirror has no unique selected registration hint.",
                 dict(evidence_source="hcpp_hint_only", differences=[dict(object=hcp.name,
                      field="matching_member_count", before=1, after=len(matches))]))
        raw, hint_source = matches[0], "hcpp_hint_only"
        try:
            mirror_rows = _rows(raw, hcp.parent)
        except BridgeError as exc:
            raise RegistrationEvidenceError("registration_needs_refresh", "The bounded mirror registration is invalid: {}".format(exc),
                context=dict(evidence_source="hcpp_hint_only", object=hcp.name, reason="invalid_registration")) from exc
        hint = comparison(hint_source, {r["id"]: r for r in rows}, {r["id"]: r for r in mirror_rows})
        hint.update(authoritative=False, possibly_stale=True,
                    matches_closed_snapshot=sha256(raw) == receipt["registration_sha256"],
                    rows_match=mirror_rows == rows, captured_sha256=receipt["registration_sha256"],
                    observed_sha256=sha256(raw), captured_row_count=len(rows), observed_row_count=len(mirror_rows),
                    archive_sha256=validation["archive_sha256"], hcp_error=str(unavailable),
                    hcp_winerror=getattr(unavailable, "winerror", None),
                    hcp_read_reason="sharing_violation" if getattr(unavailable, "winerror", None) == 32 else "access_denied")
        # Mirror differences are diagnostic only. Authority for this narrow
        # existing-target route is the unmodified receipt + independent live
        # tree/process + ALL frozen files + actual editor proof in the caller.
        # Never replace the captured rows/dependencies with the older mirror.
    if hint_source == "hcp":
        direct_rows = _rows(raw, hcp.parent)
        context = comparison("direct_hcp", {r["id"]: r for r in rows}, {r["id"]: r for r in direct_rows})
        context.update(captured_sha256=receipt["registration_sha256"], observed_sha256=sha256(raw))
        if sha256(raw) != receipt["registration_sha256"] and not context["differences"]:
            context.update(differences=[dict(object=hcp.name, field="sha256", before=receipt["registration_sha256"],
                                            after=sha256(raw))], difference_count=1)
        _require(sha256(raw) == receipt["registration_sha256"] and direct_rows == rows, "registration_stale",
                 "Direct HCP differs from the captured direct-HCP snapshot.", context)
    target, path = _target(rows, hcp.parent, program)
    _require(target == receipt["target"] and str(path) == receipt["target_path"],
             "registration_stale", "Frozen target mapping changed.")
    native_hashes = _native_hashes(hcp.parent, rows)
    _require(native_hashes == receipt["native_hashes"], "registration_stale", "Native dependency baseline changed.",
             comparison("native_files", receipt["native_hashes"], native_hashes))
    file_states = _registered_file_states(hcp.parent, rows)
    _require(file_states == receipt["registered_file_states"], "registration_stale", "Registered file baseline changed.",
             comparison("registered_files", receipt["registered_file_states"], file_states))
    return dict(project=str(hcp.parent), target=str(path), scope="existing_target_content_only",
                registration_freshness="target_verified_by_live_observation",
                registration_hint_source=hint_source, structural_mutation_authorized=False,
                current_hcp_verified=hint_source == "hcp", registration_hint=hint,
                receipt_sha256=receipt["receipt_sha256"])
