"""Explicit, experimental offline project lifecycle. Not a public service API.

No implicit save/discard, application launch/exit, compile, PLC or UI retry.
Windows libraries load only when the real driver is constructed.
"""

import hashlib
import json
from pathlib import Path
import re
import time

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.storage import create_backup
from autoshop_bridge.projects.inventory import bounded_read

VERSION_TITLE = 'AutoShop V4.11.0.5'
SOURCE_SUFFIXES = {'.st', '.fb', '.ld', '.fc', '.stru', '.gvt', '.fbi', '.hcp', '.hcpp'}


def classify_title(title, project):
    """A pathless MFC document title is transitional, never proof of identity."""
    if title == VERSION_TITLE:
        return 'closed'
    if re.fullmatch(re.escape(VERSION_TITLE) + r'\s{2,}' + re.escape(str(project)) + r'(?: - \[.*\])?',
                    title, re.IGNORECASE):
        return 'opened'
    if title.startswith(VERSION_TITLE + ' - '):
        # Both "... - " and "... - [MAIN.ST]" were observed while MFC
        # creates a document before appending the project path. This state
        # only permits waiting, never another UI action or a success verdict.
        return 'transition'
    return 'other' if title.startswith('AutoShop') else 'transition'


def _require(condition, message):
    if not condition:
        raise BridgeError('Project lifecycle: ' + message)


def _path(value):
    p = Path(value)
    _require(p.is_absolute() and '..' not in p.parts, 'absolute paths without traversal required')
    for part in (p,) + tuple(p.parents):
        _require(not part.is_symlink() and not (part.exists() and
                 getattr(part.lstat(), 'st_file_attributes', 0) & 0x400), 'reparse paths refused')
    return p.resolve()


def project_path(value):
    p = _path(value)
    _require(p.is_file() and p.suffix.lower() == '.hcp' and p.stat().st_nlink == 1,
             'one existing regular .hcp file required')
    return p


def snapshot_sha256(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=True,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


class LifecycleError(BridgeError):
    def __init__(self, message, result):
        super().__init__(message)
        self.result = result


class SnapshotObservationTimeout(BridgeError):
    """Only the read-only Scintilla modified-state query timed out (1460)."""


class FileEvidence:
    """Protect root native/registration files, not a recursive project backup."""
    def __init__(self, project_file, output):
        self.project_file = project_path(project_file)
        self.output = _path(output)
        _require(self.output != self.project_file.parent and
                 self.project_file.parent not in self.output.parents, 'output must be outside project')
        _require(not self.output.exists(), 'use a new output directory')
        for part in (self.output,) + tuple(self.output.parents):
            _require(part.name.casefold() != 'skills' and not (part / 'SKILL.md').is_file(),
                     'output cannot be in a Skill installation')
        self.output.mkdir(parents=True)
        self.sequence = 0
        self.hashes = {}

    def log(self, label, value):
        self.sequence += 1
        with (self.output / ('%02d-%s.json' % (self.sequence, label))).open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=True, indent=2, allow_nan=False)

    def prepare(self, allow_locked_hcp):
        files, skipped = [], []
        for p in sorted(self.project_file.parent.iterdir()):
            if not p.is_file() or p.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            _path(p)
            _require(p.stat().st_nlink == 1, 'hard linked native file refused')
            try:
                raw = bounded_read(p)
            except PermissionError:
                if p == self.project_file and allow_locked_hcp:
                    skipped.append(dict(file=p.name, reason='hcp_locked_before_close'))
                    continue
                raise
            digest = hashlib.sha256(raw).hexdigest()
            backup = create_backup(p, raw, self.output / 'backups', 'project_lifecycle')
            _require((backup / 'original.native').read_bytes() == raw, 'backup readback failed')
            self.hashes[str(p)] = digest
            files.append(dict(file=p.name, sha256=digest, backup=str(backup)))
        if skipped:
            _require(any(p['file'].lower() == self.project_file.with_suffix('.hcpp').name.lower()
                         for p in files), 'locked HCP requires a readable HCPP backup')
        self.log('backups', dict(files=files, skipped=skipped, recursive_backup=False,
                                 hcpp_realtime_registration_verified=False))

    def verify_baseline(self):
        for name, expected in self.hashes.items():
            p = _path(name)
            _require(p.is_file() and p.stat().st_nlink == 1, 'file identity changed since backup')
            _require(hashlib.sha256(bounded_read(p)).hexdigest() == expected,
                     'file changed since backup: ' + p.name)

    def verify_sources_unchanged(self):
        expected = {name: digest for name, digest in self.hashes.items()
                    if Path(name).suffix.lower() not in ('.hcp', '.hcpp')}
        current = {str(p.resolve()) for p in self.project_file.parent.iterdir()
                   if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES - {'.hcp', '.hcpp'}}
        _require(current == set(expected), 'native source set changed during lifecycle')
        for name, digest in expected.items():
            p = _path(name)
            _require(p.is_file() and p.stat().st_nlink == 1 and
                     hashlib.sha256(bounded_read(p)).hexdigest() == digest,
                     'native source changed during lifecycle: ' + p.name)
        return len(expected)

    def registration_ready(self):
        p = project_path(self.project_file)
        try:
            raw = bounded_read(p)
        except PermissionError:
            return False
        backup = create_backup(p, raw, self.output / 'backups', 'project_closed_registration')
        _require((backup / 'original.native').read_bytes() == raw, 'closed HCP backup failed')
        self.log('closed-hcp-readable', dict(sha256=hashlib.sha256(raw).hexdigest(), backup=str(backup)))
        return True


def run(driver, action, expected_snapshot_sha256, evidence, *, experimental=False,
        timeout=15, clock=time.monotonic, sleep=time.sleep):
    """Synchronous state machine. Driver/evidence can be injected for offline tests."""
    _require(experimental is True, 'explicit experimental=True required')
    _require(action in ('open', 'close', 'reopen'), 'unsupported action')
    _require(type(timeout) in (int, float) and 0 < timeout <= 60, 'timeout must be 0..60 seconds')
    _require(type(expected_snapshot_sha256) is str and len(expected_snapshot_sha256) == 64 and
             all(c in '0123456789abcdef' for c in expected_snapshot_sha256), 'snapshot SHA-256 required')
    phase, dispatched = 'preflight', []
    last = None
    result = dict(action=action, status='in_progress', dispatched=dispatched,
                  automatic_retry=False, automatic_rollback=False, plc_commands_sent=False,
                  source_saved_by_tool=False, original_tabs_restored=False, observed_transitions=[])

    def poll(predicate, allow_file_dialog=False, *, open_observation=False, deadline=None):
        nonlocal last
        deadline = clock() + timeout if deadline is None else deadline
        previous = None
        while True:
            _require(clock() < deadline, 'timeout; inspect state before any further operation')
            try:
                observed = driver.snapshot()
            except SnapshotObservationTimeout:
                if not open_observation:
                    raise
                # No UI action is repeated. A failed read cannot contribute
                # to stability or replace the last complete snapshot.
                previous = None
                result['read_only_snapshot_timeouts'] = result.get('read_only_snapshot_timeouts', 0) + 1
                result['final_snapshot_may_be_stale'] = True
                _require(clock() < deadline, 'timeout; complete window snapshot unavailable')
                sleep(min(.1, deadline - clock()))
                continue
            last = observed
            result['final_snapshot_may_be_stale'] = False
            _require(clock() < deadline, 'timeout; inspect state before any further operation')
            view = dict(phase=phase, state=last['state'], title=last['title'], enabled=last['enabled'])
            if not result['observed_transitions'] or result['observed_transitions'][-1] != view:
                _require(len(result['observed_transitions']) < 128, 'too many window transitions')
                result['observed_transitions'].append(view)
            _require(not last['duplicates'], 'target project is open in another window')
            _require(last['state'] != 'other', 'target window changed to another project')
            if last['dialogs']:
                _require(allow_file_dialog and driver.is_open_dialog(last), 'prompt requires user; no response sent')
            if predicate(last):
                if not open_observation or previous == last:
                    return last
                previous = last
            else:
                previous = None
            _require(clock() < deadline, 'timeout; inspect state before any further operation')
            sleep(min(.1, deadline - clock()))

    try:
        last = driver.snapshot()
        _require(snapshot_sha256(last) == expected_snapshot_sha256, 'window snapshot baseline conflict')
        identity = dict(last['identity'])
        project_file = last['project_file']
        _require(not last['dialogs'] and last['enabled'] and not last['duplicates'], 'modal or ambiguous window')
        _require(not last['dirty'] and not last['cell_edits'], 'unsaved content or active cell editing')
        required = 'closed' if action == 'open' else 'opened'
        _require(last['state'] == required, 'action requires project ' + required)
        evidence.prepare(allow_locked_hcp=required == 'opened')
        evidence.verify_baseline()
        _require(driver.snapshot() == last, 'window changed during backup')
        evidence.log('preflight', last)
        if action in ('close', 'reopen'):
            phase = 'close_dispatch'
            evidence.log(phase, dict(command='close_project', snapshot_sha256=snapshot_sha256(last)))
            dispatched.append('close_project')  # Sending may succeed even if its acknowledgement fails.
            driver.close_project()
            phase = 'close_wait'
            poll(lambda s: s['state'] == 'closed' and s['enabled'] and not s['documents'])
            evidence.log('closed-window', last)
            phase = 'hcp_release_wait'
            deadline = clock() + timeout
            while not evidence.registration_ready():
                last = driver.snapshot()
                _require(last['state'] == 'closed' and last['enabled'] and not last['dialogs'],
                         'window changed while waiting for HCP release')
                _require(clock() < deadline, 'HCP still locked after UI close; no open dispatched')
                sleep(.1)
            last = driver.snapshot()
            _require(last['state'] == 'closed' and last['enabled'] and not last['dialogs']
                     and not last['documents'] and not last['duplicates'], 'window changed after HCP release')
        if action in ('open', 'reopen'):
            phase = 'open_dispatch'
            last = driver.snapshot()
            _require(last['state'] == 'closed' and not last['dialogs'] and last['enabled'] and not last['duplicates'],
                     'window is no longer clean and closed')
            evidence.log(phase, last)
            dispatched.append('open_project_dialog')
            driver.open_project_dialog()
            phase = 'open_dialog_wait'
            poll(lambda s: bool(s['dialogs']), allow_file_dialog=True)
            phase = 'filename_readback'
            binding = driver.fill_project_filename(last)
            evidence.log('filename-readback', binding)
            phase = 'open_confirm'
            evidence.log(phase, binding)
            dispatched.append('confirm_project_filename')
            driver.confirm_project_filename(binding)
            phase = 'open_wait'
            open_deadline = clock() + timeout
            # The same file dialog may remain visible briefly after the click;
            # never confirm it twice, and stop on a replacement/error dialog.
            poll(lambda s: s['state'] == 'opened' and s['enabled'] and not s['dialogs'],
                 allow_file_dialog=True, open_observation=True, deadline=open_deadline)
            _require(not last['dirty'] and not last['cell_edits'], 'opened project has unsaved content or active cell edit')
        phase = 'native_sources_after_verify'
        result['native_source_files_verified'] = evidence.verify_sources_unchanged()
        result['native_sources_unchanged'] = True
        expected_state = 'closed' if action == 'close' else 'opened'
        if action in ('open', 'reopen'):
            phase = 'open_final_snapshot_wait'
            poll(lambda s: s['state'] == 'opened' and s['enabled'] and not s['dialogs'],
                 open_observation=True, deadline=open_deadline)
        else:
            last = driver.snapshot()
        _require(last['state'] == expected_state and last['enabled'] and not any(
                 last[k] for k in ('dirty', 'cell_edits', 'dialogs', 'duplicates')),
                 'window changed during final native verification')
        # Cached HWND/title data may still exist while WER reports a fault.
        # Require an acknowledged, read-only main-thread message plus live
        # process identity at this boundary, not merely another cached read.
        phase = 'final_process_verify'
        current = driver.verify_responsive(last)
        _require(current['identity'] == identity and current['project_file'] == project_file,
                 'process/project identity changed before lifecycle success')
        _require(current == last, 'window changed before lifecycle success')
        last = current
        result.update(status='project_' + ('reopened' if action == 'reopen' else 'opened' if action == 'open' else 'closed'),
                      final_snapshot=last, final_snapshot_sha256=snapshot_sha256(last),
                      hcp_release_verified=action in ('close', 'reopen'), phase='complete')
        evidence.log('result', result)
        return result
    except Exception as exc:
        result.update(status='project_lifecycle_stopped', phase=phase, error=str(exc),
                      ui_action_may_have_occurred=bool(dispatched), final_snapshot=last,
                      requires_inspection_before_retry=True)
        try:
            evidence.log('stopped', result)
        except Exception as audit_error:
            # Audit IO failure must never turn an already-dispatched UI action
            # into the CLI's "preflight failed, no action" result.
            result['audit_error'] = str(audit_error)
        raise LifecycleError(str(exc), result) from exc


class WindowsProjectDriver:
    def __init__(self, project_file, pid=None):
        import ctypes
        from ctypes import wintypes as w
        from autoshop_bridge.windows.editor import Win32Editor

        class ProjectWindow(Win32Editor):
            def title_matches(self, title):
                return super().title_matches(title) or title == VERSION_TITLE

        self.project_file = project_path(project_file)
        self.a = ProjectWindow(self.project_file.parent, '__project_lifecycle__', pid, require_open=False)
        self.c, self.w = ctypes, w
        a = self.a
        _require(a.text(a.main) == VERSION_TITLE or a.text(a.main).startswith(VERSION_TITLE + '  '),
                 'unsupported initial AutoShop version')
        a.user.GetDlgCtrlID.argtypes = [w.HWND]
        a.user.GetWindow.argtypes, a.user.GetWindow.restype = [w.HWND, w.UINT], w.HWND
        a.kernel.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
        a.kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        a.kernel.WaitForSingleObject.restype = w.DWORD
        a.kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        a.kernel.GetExitCodeProcess.restype = w.BOOL
        self.identity = self._identity()
        self._check_resources()
        self.open_dialog = None

    def _identity(self):
        a, c, w = self.a, self.c, self.w
        _require(a.user.IsWindow(a.main) and a.window_pid(a.main) == a.pid and a.is_autoshop(a.pid),
                 'process/window identity changed')
        handle = a.kernel.OpenProcess(0x101000, False, a.pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        _require(handle, 'cannot inspect process identity')
        try:
            _require(a.kernel.WaitForSingleObject(handle, 0) == 0x102,
                     'target process exited or its liveness cannot be verified')
            exit_code = w.DWORD()
            _require(a.kernel.GetExitCodeProcess(handle, c.byref(exit_code))
                     and exit_code.value == 259, 'target process is not active')
            exe = c.create_unicode_buffer(32768)
            size = w.DWORD(len(exe))
            _require(a.kernel.QueryFullProcessImageNameW(handle, 0, exe, c.byref(size)), 'cannot inspect process path')
            times = [w.FILETIME() for _ in range(4)]
            _require(a.kernel.GetProcessTimes(handle, *(c.byref(t) for t in times)), 'cannot inspect process start')
            _require(a.kernel.WaitForSingleObject(handle, 0) == 0x102
                     and a.user.IsWindow(a.main) and a.window_pid(a.main) == a.pid,
                     'target process/window exited during identity observation')
            return dict(pid=a.pid, main=a.main, exe=exe.value,
                        creation_time=(times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        finally:
            a.kernel.CloseHandle(handle)

    def _check_resources(self):
        a, c, w = self.a, self.c, self.w
        k = a.kernel
        k.LoadLibraryExW.argtypes, k.LoadLibraryExW.restype = [w.LPCWSTR, w.HANDLE, w.DWORD], w.HMODULE
        k.FreeLibrary.argtypes = [w.HMODULE]
        a.user.LoadStringW.argtypes = [w.HINSTANCE, w.UINT, w.LPWSTR, c.c_int]
        module = k.LoadLibraryExW(self.identity['exe'], None, 0x22)
        _require(module, 'cannot read command resources as data')
        try:
            for command, expected in ((32859, '打开一个现有工程\n打开工程'), (32860, '关闭当前工程\n关闭工程')):
                text = c.create_unicode_buffer(1024)
                _require(a.user.LoadStringW(module, command, text, len(text)) > 0 and text.value == expected,
                         'command resource differs from observed version')
        finally:
            k.FreeLibrary(module)

    def _guard(self):
        _require(self._identity() == self.identity, 'process/window reused')
        # MFC replaces its title while opening. Version/resources were checked
        # on attachment; the same HWND/PID/start-time/exe remain mandatory.
        # Only a stable exact project/idle title permits the NEXT UI action.
        project_path(self.project_file)

    def verify_responsive(self, expected):
        """One bounded WM_NULL acknowledgement; no activation or retry.

        This proves a responsive, live target at the observation instant. It
        cannot guarantee that the vendor application will never exit later.
        """
        self._guard()
        self.a.window_message(self.a.main, 0)  # WM_NULL, existing 1500ms transport bound.
        self._guard()
        current = self.snapshot()
        _require(current == expected, 'window changed during final response verification')
        return current

    def _dialogs(self):
        a = self.a
        result = []
        @a.callback_type
        def callback(h, unused):
            if a.window_pid(h) == a.pid and a.class_name(h) == '#32770' and a.user.IsWindowVisible(h):
                result.append(dict(hwnd=h, title=a.text(h)))
            return True
        _require(a.user.EnumWindows(callback, 0), 'cannot enumerate dialogs')
        return result

    def snapshot(self):
        self._guard()
        a = self.a
        title = a.text(a.main)
        state = classify_title(title, self.project_file.parent)
        documents, dirty, cell_edits = [], [], []
        for doc in a.children(a.main):
            if a.class_name(a.user.GetParent(doc)) != 'MDIClient':
                continue
            name = a.text(doc)
            documents.append(dict(hwnd=doc, title=name))
            if name.rstrip().endswith('*'):
                dirty.append(dict(document=name, reason='dirty_title'))
            for h in a.children(doc):
                cls = a.class_name(h)
                if cls == 'Scintilla' and self._snapshot_modified(h):
                    dirty.append(dict(document=name, reason='modified_scintilla', hwnd=h))
                if a.user.IsWindowVisible(h) and (cls == 'Edit' or cls.startswith('ATL:')):
                    cell_edits.append(dict(document=name, hwnd=h, cls=cls))
        duplicates = []
        @a.callback_type
        def top(h, unused):
            if h != a.main and a.title_matches(a.text(h)) and a.text(h) != VERSION_TITLE and a.is_autoshop(a.window_pid(h)):
                duplicates.append(dict(hwnd=h, pid=a.window_pid(h), title=a.text(h)))
            return True
        _require(a.user.EnumWindows(top, 0), 'cannot inspect duplicate project windows')
        result = dict(schema=1, project_file=str(self.project_file), identity=self.identity, state=state,
                    title=title, enabled=bool(a.user.IsWindowEnabled(a.main)), documents=documents,
                    dirty=dirty, cell_edits=cell_edits, dialogs=self._dialogs(), duplicates=duplicates)
        self._guard()  # Win32 enumeration may outlive the process it observed.
        return result

    def _snapshot_modified(self, handle):
        try:
            return self.a.window_message(handle, 2159)
        except BridgeError as exc:
            # The shared Win32 adapter has no typed timeout. Narrow this
            # conversion to its exact 1460 diagnostic and this scalar READ;
            # filename entry/confirmation and every other error stay fatal.
            if type(exc) is not BridgeError or str(exc) != (
                    'AutoShop editor message timed out or was denied (Windows error 1460).'):
                raise
            self._guard()
            _require(classify_title(self.a.text(self.a.main), self.project_file.parent) != 'other',
                     'target window changed to another project')
            _require(not self._dialogs(), 'prompt requires user; no response sent')
            raise SnapshotObservationTimeout(str(exc)) from exc

    def close_project(self):
        s = self.snapshot()
        _require(s['state'] == 'opened' and s['enabled'] and not any(
                 s[k] for k in ('dirty', 'cell_edits', 'dialogs', 'duplicates')), 'close preconditions changed')
        _require(self.a.user.PostMessageW(self.a.main, 0x111, 32860, 0), 'close dispatch failed')

    def open_project_dialog(self):
        s = self.snapshot()
        _require(s['state'] == 'closed' and s['enabled'] and not s['documents'] and not s['dialogs'] and not s['duplicates'],
                 'open preconditions changed')
        _require(self.a.user.PostMessageW(self.a.main, 0x111, 32859, 0), 'open dispatch failed')

    def _dialog_parts(self, snapshot):
        a = self.a
        _require(len(snapshot['dialogs']) == 1, 'exactly one file dialog required')
        dialog = snapshot['dialogs'][0]
        h = dialog['hwnd']
        _require(dialog['title'] == '打开' and a.user.IsWindow(h) and a.window_pid(h) == a.pid
                 and a.text(h) == '打开' and not a.user.IsWindowEnabled(a.main), 'unexpected file dialog')
        owner = a.user.GetWindow(h, 4)  # GW_OWNER; do not confirm another window's file dialog.
        owners = set()
        while owner and owner not in owners and owner != a.main:
            owners.add(owner)
            owner = a.user.GetWindow(owner, 4)
        _require(owner == a.main, 'file dialog is not owned by the bound AutoShop window')
        children = a.children(h)
        edits = [c for c in children if a.class_name(c) == 'Edit' and a.user.GetDlgCtrlID(c) == 1148]
        buttons = [c for c in children if a.class_name(c) == 'Button' and a.user.GetDlgCtrlID(c) == 1
                   and a.text(c) == '打开(&O)']
        _require(len(edits) == len(buttons) == 1, 'unknown file dialog controls')
        _require(a.window_pid(edits[0]) == a.pid and a.window_pid(buttons[0]) == a.pid,
                 'file dialog control process differs')
        parent = a.user.GetParent(edits[0])
        outer = a.user.GetParent(parent)
        _require(a.class_name(parent) == 'ComboBox' and a.class_name(outer) == 'ComboBoxEx32'
                 and a.user.GetParent(outer) == h and a.user.GetDlgCtrlID(outer) == 1148,
                 'unknown filename editor hierarchy')
        return dict(dialog=h, edit=edits[0], button=buttons[0])

    def is_open_dialog(self, snapshot):
        try:
            parts = self._dialog_parts(snapshot)
            return self.open_dialog is None or self.open_dialog == parts['dialog']
        except BridgeError:
            return False

    def _read_edit(self, handle):
        text = self.c.create_unicode_buffer(8192)
        self.a.window_message(handle, 0xD, len(text), self.c.addressof(text))
        return text.value

    def fill_project_filename(self, snapshot):
        _require(self.snapshot() == snapshot, 'file dialog changed before entry')
        parts = self._dialog_parts(snapshot)
        self.open_dialog = parts['dialog']
        filename = str(project_path(self.project_file))
        old = self._read_edit(parts['edit'])
        _require(old in ('', self.project_file.name, filename), 'unexpected filename; inspect before replacing')
        text = self.c.create_unicode_buffer(filename)
        _require(self.a.window_message(parts['edit'], 0xC, 0, self.c.addressof(text)), 'filename entry failed')
        _require(self._read_edit(parts['edit']) == filename, 'filename readback differs')
        return dict(parts, project_file=filename)

    def confirm_project_filename(self, binding):
        self._guard()
        current = self._dialog_parts(self.snapshot())
        _require(all(binding[k] == current[k] for k in ('dialog', 'edit', 'button')),
                 'file dialog identity changed before confirm')
        _require(binding['project_file'] == str(project_path(self.project_file))
                 and self._read_edit(binding['edit']) == binding['project_file'], 'filename changed before confirm')
        self.a.window_message(binding['button'], 0xF5)
