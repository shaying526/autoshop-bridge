"""Opt-in opaque HGLOBAL clipboard backup/restore, using an injected adapter.

No Windows objects are created here. The adapter protocol is WinClipboard's
opened/formats/data/sequence/owner_pid/replace interface. Existing default
clipboard protection is unchanged. Unknown formats are rejected before reads.

Entire allocation bytes, including any unused capacity, are private recovery
material only. They are never decoded as source or included in metadata/repr.
This preserves only the accepted format payloads; it cannot restore the former
owner, sequence, OLE objects, delayed-rendering behavior or application state.

References: Microsoft clipboard-operations / clipboard-formats; Chromium
content/public/browser/clipboard_types.cc and
ui/base/clipboard/clipboard_format_type_win.cc. Registered names are exact.
"""

from dataclasses import dataclass
import hashlib
import struct

from autoshop_bridge.errors import BridgeError

MAX_ALLOCATION_BYTES = 16 * 1024 * 1024
MAX_FORMATS = 128
STANDARD_FORMATS = frozenset((1, 7, 13, 16))  # TEXT/OEMTEXT/UNICODETEXT/LOCALE
REGISTERED_FORMAT_NAMES = frozenset(("HTML Format", "Chromium internal source RFH token",
                                   "Chromium internal source URL"))


def _require(condition, message):
    if not condition:
        raise BridgeError("HGLOBAL clipboard protection: " + message)


def _uint32(value, name):
    _require(type(value) is int and 0 <= value <= 4294967295, "invalid " + name)
    return value


def _formats(value):
    _require(type(value) is list and len(value) <= MAX_FORMATS, "invalid format enumeration")
    result, ids, registered_names = [], set(), set()
    for item in value:
        _require(type(item) is dict and set(item) == {"format", "name"}, "invalid format descriptor")
        identity, name = item["format"], item["name"]
        _require(type(identity) is int and 0 < identity <= 65535 and type(name) is str,
                 "invalid format identity/name")
        _require(identity not in ids, "duplicate format identity")
        ids.add(identity)
        if identity in STANDARD_FORMATS:
            _require(name == "", "standard format must have an empty registered name")
        else:
            _require(49152 <= identity <= 65535 and name in REGISTERED_FORMAT_NAMES,
                     "unsupported format; unknown, image, OLE, GDI and owner-display formats are refused")
            _require(name not in registered_names, "duplicate registered format name")
            registered_names.add(name)
        result.append((identity, name))
    return tuple(result)


def _read_values(clipboard, formats):
    result, total = [], 0
    for identity, _ in formats:
        value = clipboard.data(identity)
        _require(type(value) is bytes and 0 < len(value) <= MAX_ALLOCATION_BYTES,
                 "invalid allocation bytes or per-format size limit exceeded")
        total += len(value)
        _require(total <= MAX_ALLOCATION_BYTES, "combined allocation size exceeds 16 MiB")
        result.append(value)
    return tuple(result)


def _fingerprint(sequence, owner_pid, formats, values):
    digest = hashlib.sha256(struct.pack("<II", sequence, owner_pid))
    for (identity, name), value in zip(formats, values):
        encoded = name.encode("utf-8")
        digest.update(struct.pack("<III", identity, len(encoded), len(value)))
        digest.update(encoded)
        digest.update(value)
    return digest.hexdigest()


@dataclass(frozen=True, repr=False)
class ClipboardSnapshot:
    """Private recovery bytes; deliberately not a JSON serializable export."""

    sequence: int
    owner_pid: int
    _formats: tuple
    _values: tuple
    _fingerprint: str

    def __repr__(self):
        return "<ClipboardSnapshot formats={} allocation_bytes={} private_recovery_only>".format(
            len(self._formats), sum(map(len, self._values)))

    def as_dict(self):
        """Bounded metadata only; no raw bytes, URLs, token or clipboard text."""
        _validate_snapshot(self)
        return dict(status="hglobal_clipboard_backup_only", sequence=self.sequence,
                    owner_pid=self.owner_pid,
                    total_allocation_bytes=sum(map(len, self._values)),
                    formats=[dict(format=identity, name=name, allocation_bytes=len(value),
                                  sha256=hashlib.sha256(value).hexdigest())
                             for (identity, name), value in zip(self._formats, self._values)],
                    raw_bytes_included=False, source_export=False,
                    original_owner_restoration_claimed=False,
                    original_sequence_restoration_claimed=False)


def _validate_snapshot(snapshot):
    _require(type(snapshot) is ClipboardSnapshot, "invalid backup object")
    _uint32(snapshot.sequence, "backup sequence")
    _uint32(snapshot.owner_pid, "backup owner PID")
    _require(type(snapshot._formats) is tuple and type(snapshot._values) is tuple
             and len(snapshot._formats) == len(snapshot._values), "invalid backup records")
    _require(all(type(entry) is tuple and len(entry) == 2 for entry in snapshot._formats),
             "invalid backup format records")
    _formats([dict(format=identity, name=name) for identity, name in snapshot._formats])
    _require(all(type(v) is bytes and 0 < len(v) <= MAX_ALLOCATION_BYTES for v in snapshot._values)
             and sum(map(len, snapshot._values)) <= MAX_ALLOCATION_BYTES, "invalid backup byte sizes")
    _require(snapshot._fingerprint == _fingerprint(snapshot.sequence, snapshot.owner_pid,
                                                  snapshot._formats, snapshot._values),
             "backup integrity check failed")


def _state(clipboard):
    return (_uint32(clipboard.sequence(), "clipboard sequence"),
            _uint32(clipboard.owner_pid(), "clipboard owner PID"))


def _assert_state(clipboard, sequence, owner_pid, phase):
    actual_sequence, actual_owner = _state(clipboard)
    _require(actual_sequence == sequence and actual_owner == owner_pid
             and clipboard.sequence() == sequence, "clipboard changed " + phase + "; no retry")


def _capture_opened(clipboard):
    sequence, owner_pid = _state(clipboard)
    formats = _formats(clipboard.formats())
    values = _read_values(clipboard, formats)
    _assert_state(clipboard, sequence, owner_pid, "while taking backup")
    _require(_formats(clipboard.formats()) == formats, "format order/set changed while taking backup")
    _require(_read_values(clipboard, formats) == values, "allocation bytes changed while taking backup")
    _require(_formats(clipboard.formats()) == formats, "format order/set changed after byte verification")
    _assert_state(clipboard, sequence, owner_pid, "after backup verification")
    return ClipboardSnapshot(sequence, owner_pid, formats, values,
                             _fingerprint(sequence, owner_pid, formats, values))


def snapshot_hglobal(clipboard):
    """Capture an accepted clipboard once; refuse instability without retrying.

    GetClipboardData can request delayed rendering. Such rendering may change
    observable clipboard state; if it does, this operation refuses the result.
    No clipboard mutation is issued by this helper.
    """
    with clipboard.opened():
        result = _capture_opened(clipboard)
    _assert_state(clipboard, result.sequence, result.owner_pid, "after closing backup read")
    return result


def _same_payload(actual, expected):
    _require(actual._formats == expected._formats, "restored format order/set/names do not match original")
    _require(actual._values == expected._values, "restored allocation bytes do not match original")


def restore_hglobal(clipboard, snapshot, *, expected_current_sequence, expected_owner_pid):
    """Replace once and verify full format/payload equality, including reopen.

    The caller must authenticate the intervening copy's sequence and owner.
    This function never retries, overwrites a detected newer clipboard, or
    attempts a second restore after partial failure. A replace/read-back error
    may leave partially restored contents and must be handled as a failure.
    """
    _validate_snapshot(snapshot)
    _uint32(expected_current_sequence, "expected current sequence")
    _uint32(expected_owner_pid, "expected current owner PID")
    with clipboard.opened():
        _assert_state(clipboard, expected_current_sequence, expected_owner_pid, "before restoration")
        try:
            clipboard.replace({identity: value for (identity, _), value
                               in zip(snapshot._formats, snapshot._values)})
        except Exception as exc:
            raise BridgeError("HGLOBAL clipboard protection: restore adapter failed; clipboard may be "
                              "partially restored; no retry") from exc
        restored = _capture_opened(clipboard)
        _require(restored.sequence != expected_current_sequence,
                 "restoration did not change clipboard sequence; outcome unverified")
        _same_payload(restored, snapshot)
    # Closing the clipboard can trigger synthesized text formats. Read again,
    # rather than treating a successful SetClipboardData as restored evidence.
    reopened = snapshot_hglobal(clipboard)
    _require((reopened.sequence, reopened.owner_pid) == (restored.sequence, restored.owner_pid),
             "clipboard changed after restoration; no retry")
    _same_payload(reopened, snapshot)
    return dict(status="hglobal_clipboard_restored_verified", format_count=len(snapshot._formats),
                total_allocation_bytes=sum(map(len, snapshot._values)),
                restored_sequence=reopened.sequence, restored_owner_pid=reopened.owner_pid,
                format_order_set_and_names_verified=True, allocation_bytes_verified=True,
                verified_after_reopen=True, raw_bytes_included=False, source_export=False,
                original_owner_restoration_claimed=False,
                original_sequence_restoration_claimed=False)
