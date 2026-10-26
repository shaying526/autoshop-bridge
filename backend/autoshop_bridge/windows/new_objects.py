"""Normal AutoShop FB/structure creation, with explicit per-object receipts.

Windows imports and session attachment are deferred until construction. No
native serializer, project switch, lifecycle action, compile or PLC call here.
"""
import ctypes
import json
import time
from pathlib import Path

from autoshop_bridge.errors import BridgeError, ConflictError
from autoshop_bridge.formats.native import parse
from autoshop_bridge.formats.tables import parse as parse_table, comment_display
from autoshop_bridge.projects.inventory import bounded_read, scan, select_project
from autoshop_bridge.storage import create_backup, regular_file, writable_target, sha256, write_json_new, write_new
from autoshop_bridge.windows.creation import WindowsNewSTDialog, mirror_state

SOURCE_SUFFIXES = {'.st', '.fb', '.fc', '.ld', '.stru', '.gvt', '.fbi'}


def require(value, message):
    if not value:
        raise BridgeError('Object creation: ' + message)


def _saved_mirror_changed(mirror, before):
    """Only observe a dispatched save; its writer can briefly deny sharing."""
    try:
        return sha256(bounded_read(mirror)) != sha256(before)
    except PermissionError as exc:
        if getattr(exc, 'winerror', None) in (32, 33):
            return False
        raise


class NewFBDialog(WindowsNewSTDialog):
    CATEGORY = '功能块(FB)'
    DIALOG_PROFILE = 'autoshop-4.11.0.5-new-litest-fb'


class NewStructureDialog(WindowsNewSTDialog):
    CATEGORY = '结构体'
    DIALOG_PROFILE = 'autoshop-4.11.0.5-new-structure'
    LANGUAGE_VISIBLE = False

    def configure(self, name):
        # The observed structure dialog hides both language controls. Do not
        # manipulate a hidden language selector as if this were a program.
        text = ctypes.create_unicode_buffer(name)
        require(self.session.window_message(self.controls[2816], 0xC, 0, ctypes.addressof(text)),
                'Structure name rejected')


class WindowsObjectCreation:
    def __init__(self, project, pid=None, backup_root=None):
        from autoshop_bridge.windows.project_lifecycle import WindowsProjectDriver
        self.hcp = select_project(Path(project))
        self.project = self.hcp.parent
        self.driver = WindowsProjectDriver(self.hcp, pid)
        self.identity = dict(self.driver.identity)
        self.pid = self.identity['pid']
        self.backup_root = Path(backup_root).resolve() if backup_root else self.project.parent / 'object-creation-backups'
        require(self.backup_root != self.project and self.project not in self.backup_root.parents,
                'Creation backups must be outside the native project')
        self.dialog = None
        self.sequence = 0
        self.expected_initial = None

    def source_hashes(self):
        result = {}
        # Registered subdirectories are covered by the matched mirror below;
        # additionally reject unregistered root sources/name conflicts.
        paths = set(p for p in self.project.iterdir() if p.suffix.lower() in SOURCE_SUFFIXES)
        state = mirror_state(self.project)
        paths.update(self.project / name for name in state['matched'] if Path(name).suffix.lower() in SOURCE_SUFFIXES)
        for p in sorted(paths):
            p = regular_file(p)
            require(self.project in p.parents, 'Native path leaves the selected project')
            result[p.relative_to(self.project).as_posix()] = sha256(bounded_read(p))
        return result, state

    def snapshot(self):
        s = self.driver.snapshot()
        require(s['identity'] == self.identity and s['state'] == 'opened' and not s['duplicates'],
                'Exact project/process must remain open and unique')
        require(s['enabled'], 'Unknown modal dialog is open')
        hashes, state = self.source_hashes()
        self.baseline_state = state
        names = [value for node in state['root'].findall('file')
                 for value in [node.findtext('Caption') or Path(node.findtext('FileName') or '').stem] if value]
        return dict(project=str(self.project), identity=dict(self.identity), native_hashes=hashes,
                    registration_sha256=sha256(state['raw']), object_names=names,
                    dirty_documents=s['dirty'], dialogs=s['dialogs'], cell_edits=s['cell_edits'])

    def backup(self, plan):
        state = self.baseline_state
        path = create_backup(state['mirror'], state['raw'], self.backup_root, 'before_ui_object_creation')
        write_new(path / 'registration_from_mirror.hcp', state['saved_hcp'])
        write_json_new(path / 'plan.json', plan)
        sources = []
        for relative, expected in plan['baseline']['native_hashes'].items():
            target = regular_file(self.project / relative)
            raw = bounded_read(target)
            require(sha256(raw) == expected, 'Source changed while backing up')
            saved = create_backup(target, raw, path / 'native', 'before_ui_object_creation')
            sources.append(dict(file=relative, sha256=expected, backup=str(saved)))
        write_json_new(path / 'sources.json', sources)
        self.plan = plan
        return dict(path=str(path), verified=True, unique=True, source_count=len(sources),
                    registration_source='verified_saved_mirror', direct_hcp_verified=state['direct_hcp_verified'])

    def record(self, backup, value):
        self.sequence += 1
        write_json_new(Path(backup['path']) / ('%03d-stage.json' % self.sequence), value)

    def _tree(self, a):
        trees = []
        for h in a.children(a.main):
            if a.class_name(h) != 'SysTreeView32': continue
            ancestor = a.user.GetParent(h)
            while ancestor and ancestor != a.main:
                if a.text(ancestor) == '工程管理': trees.append(h); break
                ancestor = a.user.GetParent(ancestor)
        require(len(trees) == 1, 'Exactly one project-management tree required')
        return trees[0]

    def _popups(self, a):
        found = []
        @a.callback_type
        def top(h, unused):
            if (a.window_pid(h) == self.pid and a.user.IsWindowVisible(h) and
                a.user.GetParent(h) == a.main and ':800:' in a.class_name(h) and not a.text(h)):
                found.append(h)
            return True
        require(a.user.EnumWindows(top, 0), 'Cannot inspect normal context popup')
        return found

    @staticmethod
    def _wait(check, message):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            result = check()
            if result: return result
            time.sleep(.05)
        raise BridgeError('Object creation: timed out waiting for ' + message)

    def open_dialog(self, kind):
        from autoshop_bridge.windows.session import WindowsSession
        cls = NewFBDialog if kind == 'litest_fb' else NewStructureDialog
        require(self.snapshot() == self.plan['baseline'], 'Baseline changed before dialog navigation')
        a = WindowsSession(self.project, cls.CATEGORY, self.pid)
        a.user.IsIconic.argtypes = [ctypes.c_void_p]
        a.user.IsIconic.restype = ctypes.c_bool
        require(not a.user.IsIconic(a.main), 'Restore the target AutoShop window before creation')
        require(not self._popups(a), 'Unexpected existing context popup')
        require(a.accessible('tree_context_keyboard', self._tree(a)) == 'context_posted', 'Creation category was not selected')
        def popup():
            self.driver._guard()
            require(not self.driver._dialogs(), 'Unexpected modal before normal creation command')
            rows = self._popups(a)
            require(len(rows) <= 1, 'Ambiguous context popup')
            return rows[0] if rows else None
        h = self._wait(popup, 'owned category popup')
        # Verified V4.11.0.5 normal category menus: Home selects New FB / New
        # data structure. This only opens a dialog; strict category, controls,
        # visibility, name/language and disk guards precede actual submission.
        require(a.user.PostMessageW(h, 0x100, 36, 0), 'Cannot select normal New command')
        time.sleep(.1)
        require(popup() == h, 'Popup changed before New command')
        require(a.user.PostMessageW(h, 0x100, 13, 0), 'Cannot open normal New dialog')
        self._wait(lambda: self.driver._dialogs(), 'normal New dialog')
        self.dialog = cls(self.project, self.pid)
        initial = self.dialog.inspect()
        require(not initial['dirty_documents'], 'Existing dirty document before creation')
        self.dialog_initial = initial

    def configure_dialog(self, kind, name):
        self.dialog.configure(name)
        state = self.dialog.inspect()
        require(state['dialog_hwnd'] == self.dialog_initial['dialog_hwnd'] and state['name'] == name
                and state['selected_language'] == '结构化文本(LiteST)' and not state['dirty_documents'],
                'Configured creation dialog differs')
        self.configured = state

    def guard_before_submit(self, plan):
        self.driver._guard()
        require(self.dialog.inspect() == self.configured, 'Creation dialog changed before submission')
        hashes, state = self.source_hashes()
        require(hashes == plan['baseline']['native_hashes'] and sha256(state['raw']) == plan['baseline']['registration_sha256'],
                'Native/registration baseline changed before submission')
        require(not any(p.stem.casefold() == plan['name'].casefold() for p in self.project.iterdir()),
                'New object name is occupied on disk')

    def submit_dialog(self):
        self.driver._guard()
        self.dialog.submit()

    def _target(self, plan):
        suffix = '.fb' if plan['kind'] == 'litest_fb' else '.stru'
        paths = [p for p in self.project.iterdir() if p.stem.casefold() == plan['name'].casefold() and p.suffix.lower() == suffix]
        require(len(paths) == 1, 'Exactly one newly created native object required')
        return regular_file(paths[0])

    def observe(self, plan):
        # Creation initializes document defaults asynchronously. Repeat only a
        # read if the native bytes changed during that read, never creation.
        for unused in range(3):
            result = self._observe_once(plan)
            if sha256(bounded_read(self._target(plan))) == result['native_sha256']:
                return result
            time.sleep(.1)
        raise ConflictError('New object did not stabilize during read-only observation.')

    def _observe_once(self, plan):
        self.driver._guard()
        target = self._target(plan)
        raw = bounded_read(target)
        result = dict(created=True, actual_name=target.stem, native_path=str(target), native_sha256=sha256(raw),
                      language='ST' if plan['kind'] == 'litest_fb' else None, saved=False,
                      native_readback_verified=False, editor_readback_verified=False,
                      registration_verified=False, registration_source=None)
        require(raw.startswith(b'AutoShop'), 'New object does not have an AutoShop header')
        inv = scan(self.project)
        rows = [r for r in inv['files'] if r.get('path') == str(target) and r.get('kind') ==
                ('function_block' if plan['kind'] == 'litest_fb' else 'structure')]
        result.update(registration_verified=len(rows) == 1, registration_source=inv['registration_source'])
        try:
            if plan['kind'] == 'litest_fb':
                from autoshop_bridge.windows.session import WindowsSession
                a = WindowsSession(self.project, target.stem, self.pid)
                body = a.read(); obj = parse(raw, 'fb')
                result.update(saved=not body.modified and not a.dirty(),
                              native_readback_verified=obj.program_name == target.stem and obj.source.decode('utf-8') == plan['initial']['source'],
                              editor_readback_verified=body.source.decode('utf-8') == plan['initial']['source'],
                              variable_count=len(obj.variables))
            else:
                from autoshop_bridge.windows.table_session import WindowsTableSession, assert_native_table
                a = WindowsTableSession(self.project, target.stem, 'stru', self.pid)
                obj = parse_table(raw, 'stru'); rows = a.grid(); assert_native_table(obj, rows)
                expected = plan['initial']['members']
                actual = [dict(name=r.name, data_type=r.type_text or {1:'BOOL',4:'INT',16:'DINT'}.get(r.type_code), comment=comment_display(r.comment)) for r in obj.rows]
                expected = [dict(row, comment=comment_display(row['comment'])) for row in expected]
                result.update(saved=not a.dirty(), member_count=len(rows),
                              native_readback_verified=obj.name == target.stem and actual == expected,
                              editor_readback_verified=actual == expected)
        except BridgeError as exc:
            result['readback_error'] = str(exc)
        return result

    def initialize(self, plan, observed, backup):
        self.driver._guard()
        target = writable_target(self._target(plan)); raw = bounded_read(target)
        require(sha256(raw) == observed['native_sha256'], 'New object changed before initialization')
        saved = create_backup(target, raw, self.backup_root, 'new_object_before_initial_content')
        self.record(backup, dict(stage='initial_content_backup', path=str(saved), native_sha256=sha256(raw)))
        if plan['kind'] == 'litest_fb':
            from autoshop_bridge.windows.session import WindowsSession
            a = WindowsSession(self.project, target.stem, self.pid)
            before = a.read()
            require(not before.source and not before.modified and not a.dirty(), 'New FB editor must be clean and empty')
            content = plan['initial']['source'].encode('utf-8')
            self.verify_existing(plan)
            require(target.read_bytes() == raw, 'New FB disk changed before initial write')
            a.write(content)
            require(a.read().source == content and a.dirty() and target.read_bytes() == raw,
                    'New FB initial buffer proof failed')
            a.save()
        else:
            from autoshop_bridge.windows.table_session import WindowsTableSession, add_row, assert_native_table
            a = WindowsTableSession(self.project, target.stem, 'stru', self.pid)
            a.ensure_open(True)
            obj = parse_table(raw, 'stru'); current = a.grid(); assert_native_table(obj, current)
            require(not a.dirty(), 'New structure must have no unsaved content')
            members = plan['initial']['members']
            if current:
                default = [dict(row='1',name='member_1',data_type='BOOL',comment='',id='1')]
                require(current == default and len(obj.rows) == 1 and obj.name == target.stem,
                        'Unknown initial structure defaults')
                current = initialize_default_member(a, current, members[0])
                members = members[1:]
            else:
                require(not obj.rows, 'Empty structure editor/native mismatch')
            for member in members:
                self.driver._guard(); self.verify_existing(plan)
                require(target.read_bytes() == raw, 'Structure changed before member edit')
                current = add_row(a, current, dict(op='add', **member), 'stru')
            a.save()
            require(a.grid() == current and not a.dirty(), 'Saved initial members differ')

    def verify_existing(self, plan):
        self.driver._guard()
        baseline = plan['baseline']['native_hashes']
        for name, expected in baseline.items():
            require(sha256(bounded_read(regular_file(self.project / name))) == expected, 'Existing source changed: ' + name)
        created = self._target(plan)
        for p in self.project.iterdir():
            if p.suffix.lower() in SOURCE_SUFFIXES:
                require(p.name in baseline or p == created, 'Unexpected additional source: ' + p.name)

    def save_project(self, plan, backup):
        # Separate explicit plan option: ordinary creation never silently saves
        # the entire project. Reject every dirty document/cell/unknown prompt.
        require(plan['save_project'] is True, 'Project-save permission missing from plan')
        s = self.driver.snapshot()
        require(s['identity'] == self.identity and s['state'] == 'opened' and s['enabled'] and
                not any(s[k] for k in ('dirty','dialogs','cell_edits','duplicates')),
                'Project save requires no unsaved user documents or active cell')
        self.verify_existing(plan)
        mirror = self.hcp.with_suffix('.hcpp'); before = bounded_read(regular_file(mirror))
        protected = create_backup(mirror, before, self.backup_root, 'before_explicit_project_registration_save')
        self.record(backup, dict(stage='project_save_dispatch', mirror_backup=str(protected), command=32861))
        self.driver._guard()
        require(self.driver.a.user.PostMessageW(self.driver.a.main,0x111,32861,0), 'Project-save dispatch failed')
        def refreshed():
            self.driver._guard()
            require(not self.driver._dialogs(), 'Unknown prompt after project-save request')
            return _saved_mirror_changed(mirror, before)
        self._wait(refreshed, 'saved registration mirror update; do not repeat save blindly')
        self.verify_existing(plan)


def initialize_default_member(adapter, before, member):
    """Only the observed software-created member_1/BOOL/id1, never user rows."""
    import copy
    require(before == [dict(row='1',name='member_1',data_type='BOOL',comment='',id='1')],
            'Exact software-created initial member required')
    current = copy.deepcopy(before)
    for field, value in (('name', member['name']), ('data_type', member['data_type']),
                         ('comment', comment_display(member['comment']))):
        old = current[0][field]
        if value == old: continue
        identity = current[0]['name']
        desired = copy.deepcopy(current); desired[0][field] = value
        actual = adapter.set_cell(identity, field, old, value)
        require(actual == desired, 'Initial member full-row verification failed after ' + field)
        current = actual
    return current


def plan(project, kind, name, source_file=None, members_file=None, pid=None, output=None, save_project=False, backend=None):
    from autoshop_bridge.workflows.object_creation import ObjectCreationWorkflow
    if kind == 'litest-fb': kind = 'litest_fb'
    try:
        source = bounded_read(regular_file(Path(source_file))).decode('utf-8-sig') if source_file is not None else None
        members = json.loads(bounded_read(regular_file(Path(members_file))).decode('utf-8-sig')) if members_file is not None else None
    except (UnicodeError, ValueError) as exc:
        raise BridgeError('Initial content must be UTF-8 source or a JSON member list: ' + str(exc)) from exc
    adapter = backend or WindowsObjectCreation(project, pid)
    result = ObjectCreationWorkflow(adapter).prepare(kind, name, source=source, members=members,save_project=save_project)
    if output:
        output = Path(output)
        project_root = Path(result['plan']['baseline']['project'])
        if not output.is_absolute() or output == project_root or project_root in output.parents:
            raise BridgeError('Creation plan output must be an absolute path outside the native project.')
        write_json_new(output, result['plan'])
        return dict(status=result['status'], plan_file=str(Path(output).resolve()),
                    plan_sha256=result['plan']['plan_sha256'], created=False, saved=False,
                    compile_outcome='not_run')
    return result


def create(plan_file, experimental=False, backup_root=None, backend=None):
    from autoshop_bridge.workflows.object_creation import ObjectCreationWorkflow, validate_plan
    from autoshop_bridge.storage import read_json, target_lock
    value = read_json(Path(plan_file))
    validate_plan(value)
    if not experimental: raise BridgeError('Object creation requires --experimental.')
    baseline = value['baseline']
    adapter = backend or WindowsObjectCreation(baseline['project'], baseline['identity']['pid'], backup_root)
    with target_lock(select_project(Path(baseline['project']))):
        return ObjectCreationWorkflow(adapter).create(value, experimental=True)
