"""Explicit closed-HCP project baselines, separate from target body receipts.

A baseline records bytes and identities; it grants no live write permission.
The caller supplies trusted closed-session observations and a scoped provider
that independently verifies the current process/tree before returning rows.
Unknown HCPP bytes are neither decoded here nor accepted as registration.
"""

import base64
import binascii
import copy
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
import re

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.projects import inventory
from autoshop_bridge.projects import registration_evidence as evidence
from autoshop_bridge.storage import read_json, regular_file, sha256, utc_now

SCHEMA = "autoshop-project-registration-baseline-experimental-v1"
SCOPE = "project_registration_baseline"
SOURCE = "direct_closed_hcp"
RECEIPT_KEYS = {
    "schema", "scope", "source", "project_file", "registration_raw_b64",
    "registration_sha256", "registration_rows", "tree_objects", "native_hashes",
    "registered_file_states", "closed_identity", "captured_at", "receipt_sha256",
}
_provider = ContextVar("autoshop_project_registration_provider", default=None)
_require = evidence._require


def _safe_hcp(project):
    hcp = regular_file(inventory.select_project(Path(project)))
    _require(hcp.stat().st_nlink == 1, "registration_identity_mismatch",
             "Project registration has multiple hard links.")
    return hcp


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _raw(receipt):
    value = receipt["registration_raw_b64"]
    _require(isinstance(value, str) and len(value) <= ((inventory.MAX_NATIVE_SIZE + 2) // 3) * 4,
             "registration_needs_refresh", "Invalid bounded registration base64.")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise evidence.RegistrationEvidenceError(
            "registration_needs_refresh", "Invalid registration base64.") from exc
    _require(0 < len(raw) <= inventory.MAX_NATIVE_SIZE
             and base64.b64encode(raw).decode("ascii") == value,
             "registration_needs_refresh", "Registration base64 is empty, oversized or noncanonical.")
    return raw


def capture(project, closed_observation):
    """Freeze direct HCP and every registered file, without requiring a target.

    No close/save is dispatched. The observation must come from the real
    lifecycle adapter; a title or a user-edited JSON file is not such proof.
    """
    hcp = _safe_hcp(project)
    identity = evidence._observation(closed_observation, hcp, "closed")
    _require(closed_observation.get("duplicates", []) == [], "registration_identity_mismatch",
             "Duplicate project sessions prevent a closed registration capture.")
    try:
        raw = inventory._read_hcp(hcp)
    except PermissionError as exc:
        raise evidence.RegistrationEvidenceError(
            "registration_needs_refresh", "Direct closed HCP is unavailable; no mirror can issue a baseline.") from exc
    rows = evidence._rows(raw, hcp.parent)
    trees = evidence._tree_objects(rows)
    hashes = evidence._native_hashes(hcp.parent, rows)
    states = evidence._registered_file_states(hcp.parent, rows)
    _require(inventory._read_hcp(hcp) == raw
             and evidence._native_hashes(hcp.parent, rows) == hashes
             and evidence._registered_file_states(hcp.parent, rows) == states,
             "registration_stale", "Registration or files changed during project baseline capture.")
    receipt = dict(schema=SCHEMA, scope=SCOPE, source=SOURCE, project_file=str(hcp),
                   registration_raw_b64=base64.b64encode(raw).decode("ascii"),
                   registration_sha256=sha256(raw), registration_rows=rows,
                   tree_objects=trees, native_hashes=hashes, registered_file_states=states,
                   closed_identity=identity, captured_at=utc_now())
    receipt["receipt_sha256"] = evidence._digest(receipt)
    return load(receipt)


def load(value):
    """Validate complete baseline metadata; never infer missing keys or scope.

    The embedded rows/tree are re-derived from the exact stored HCP bytes.
    File hashes are checked for structure here; verify_files checks the disk.
    The digest detects accidental changes, not an adversarially forged file.
    """
    try:
        receipt = copy.deepcopy(value) if isinstance(value, dict) else read_json(Path(value))
    except (OSError, BridgeError, TypeError, ValueError) as exc:
        raise evidence.RegistrationEvidenceError(
            "registration_needs_refresh", "Project baseline metadata cannot be read.") from exc
    _require(isinstance(receipt, dict) and set(receipt) == RECEIPT_KEYS,
             "registration_needs_refresh", "An explicit complete project registration baseline is required.")
    body = {key: val for key, val in receipt.items() if key != "receipt_sha256"}
    try:
        digest = evidence._digest(body)
    except (TypeError, ValueError) as exc:
        raise evidence.RegistrationEvidenceError(
            "registration_needs_refresh", "Project baseline is not canonical JSON metadata.") from exc
    _require(_hash(receipt["receipt_sha256"]) and receipt["receipt_sha256"] == digest
             and receipt["schema"] == SCHEMA and receipt["scope"] == SCOPE and receipt["source"] == SOURCE,
             "registration_needs_refresh", "Project baseline digest, schema, source or scope is invalid.")
    name = receipt["project_file"]
    _require(isinstance(name, str) and Path(name).is_absolute(),
             "registration_identity_mismatch", "Project baseline requires an absolute HCP path.")
    try:
        hcp = _safe_hcp(name)
    except (OSError, BridgeError) as exc:
        raise evidence.RegistrationEvidenceError(
            "registration_identity_mismatch", "Project baseline HCP path is unsafe or unavailable.") from exc
    _require(str(hcp) == name, "registration_identity_mismatch", "Project baseline HCP path is not canonical.")
    evidence._identity(receipt["closed_identity"])
    try:
        captured_at = datetime.fromisoformat(receipt["captured_at"])
    except (TypeError, ValueError) as exc:
        raise evidence.RegistrationEvidenceError(
            "registration_needs_refresh", "Project baseline capture time is invalid.") from exc
    _require(captured_at.tzinfo is not None, "registration_needs_refresh", "Capture time requires an explicit timezone.")
    raw = _raw(receipt)
    _require(_hash(receipt["registration_sha256"]) and sha256(raw) == receipt["registration_sha256"],
             "registration_needs_refresh", "Stored direct-HCP bytes do not match their hash.")
    rows = evidence._rows(raw, hcp.parent)
    _require(rows == receipt["registration_rows"] and evidence._tree_objects(rows) == receipt["tree_objects"],
             "registration_needs_refresh", "Stored registration rows/tree differ from direct-HCP bytes.")
    expected_files = {Path(*inventory.member_path(row["file"])).as_posix()
                      for row in rows if row["file"]}
    states = receipt["registered_file_states"]
    _require(isinstance(states, dict) and set(states) == expected_files,
             "registration_needs_refresh", "Registered file baseline set differs from direct HCP.")
    for state in states.values():
        _require(isinstance(state, dict) and (
            state == {"state": "missing"} or
            (set(state) == {"state", "sha256"} and state["state"] == "present" and _hash(state["sha256"]))),
            "registration_needs_refresh", "Invalid registered file state/hash.")
    hashes = receipt["native_hashes"]
    _require(isinstance(hashes, dict), "registration_needs_refresh", "Invalid native hash baseline.")
    for relative, digest in hashes.items():
        _require(isinstance(relative, str) and _hash(digest), "registration_needs_refresh", "Invalid native file/hash.")
        parts = inventory.member_path(relative)
        path = hcp.parent.joinpath(*parts)
        _require(Path(*parts).as_posix() == relative and path.suffix.lower() in evidence.SOURCE_SUFFIXES
                 and (relative in expected_files or len(parts) == 1),
                 "registration_needs_refresh", "Native baseline path is outside its registered/root scope.")
    for relative, state in states.items():
        if Path(relative).suffix.lower() in evidence.SOURCE_SUFFIXES:
            _require(state.get("state") == "present" and hashes.get(relative) == state.get("sha256"),
                     "registration_needs_refresh", "Registered native file has no matching readable baseline.")
    return receipt


def verify_files(receipt):
    """Verify disk baselines; a locked direct HCP still needs independent live proof.

    This deliberately does not fall back to an HCPP or grant structural edits.
    All frozen files and the additional root native set must remain unchanged.
    """
    receipt = load(receipt)
    hcp = Path(receipt["project_file"])
    direct = True
    try:
        raw = inventory._read_hcp(hcp)
    except PermissionError:
        direct = False
    else:
        _require(raw == _raw(receipt), "registration_stale", "Direct HCP changed since baseline capture.",
                 dict(evidence_source="direct_hcp", before=receipt["registration_sha256"], after=sha256(raw)))
    rows = receipt["registration_rows"]
    hashes = evidence._native_hashes(hcp.parent, rows)
    _require(hashes == receipt["native_hashes"], "registration_stale", "Native files or extra source set changed.",
             evidence.comparison("native_files", receipt["native_hashes"], hashes))
    states = evidence._registered_file_states(hcp.parent, rows)
    _require(states == receipt["registered_file_states"], "registration_stale", "Registered file baseline changed.",
             evidence.comparison("registered_files", receipt["registered_file_states"], states))
    return dict(project_file=str(hcp), scope=SCOPE, current_hcp_verified=direct,
                registration_sha256=receipt["registration_sha256"], receipt_sha256=receipt["receipt_sha256"],
                live_registration_verified=False)


def current():
    """Return the explicitly bound provider, never a provider from disk metadata."""
    return _provider.get()


@contextmanager
def scoped(provider):
    """Bind a caller-owned provider only for this context, including exception exits."""
    if provider is not None and not callable(getattr(provider, "get_registration", None)):
        raise BridgeError("Registration provider requires get_registration(hcp).")
    token = _provider.set(provider)
    try:
        yield provider
    finally:
        _provider.reset(token)


def registration_for(hcp):
    """Delegate to the active live provider; the registry itself grants nothing."""
    provider = current()
    return None if provider is None else provider.get_registration(hcp)
