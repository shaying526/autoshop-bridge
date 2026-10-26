"""Receipt-bound object creation; the injected adapter owns all IDE effects.

AutoShop, never this workflow, creates native containers and registration.
There is no implicit retry, rollback, compilation or project switching.
"""
import copy
import json
import re
from pathlib import Path, PureWindowsPath

from autoshop_bridge.errors import BridgeError, ConflictError
from autoshop_bridge.formats.st import validate_program_edit
from autoshop_bridge.formats.tables import addition
from autoshop_bridge.projects.identifiers import require_new_identifier, precheck_addition_names
from autoshop_bridge.storage import sha256

PROFILE = 'autoshop-ui-object-creation-v1'
KINDS = ('litest_fb', 'structure')


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode('ascii'))


def object_name(name, existing_names=()):
    require_new_identifier(name, existing_names=existing_names)
    precheck_addition_names(dict(operations=[dict(op='add', name=name)]))
    reserved = {'CON','PRN','AUX','NUL'} | {prefix+str(i) for prefix in ('COM','LPT') for i in range(1,10)}
    if name.upper() in reserved:
        raise BridgeError('Object name is a reserved Windows file name.')


def initial_content(kind, source, members):
    if kind == 'litest_fb':
        if members is not None or not isinstance(source, str) or not source.strip():
            raise BridgeError('LiteST FB creation requires nonempty source and no members.')
        validate_program_edit(source.encode('utf-8'))
        return dict(source=source)
    if kind != 'structure' or source is not None or not isinstance(members, list) or not 1 <= len(members) <= 32:
        raise BridgeError('Structure creation requires 1..32 initial scalar members and no source.')
    names = []
    for row in members:
        if not isinstance(row, dict) or set(row) != {'name', 'data_type', 'comment'}:
            raise BridgeError('Initial members require name, data_type and comment.')
        require_new_identifier(row['name'], existing_names=names)
        precheck_addition_names(dict(operations=[dict(op='add', name=row['name'])]))
        addition(dict(op='add', **row), 'stru')
        names.append(row['name'])
    return dict(members=copy.deepcopy(members))


def validate_plan(plan):
    keys = {'schema', 'profile', 'kind', 'name', 'initial', 'baseline', 'save_project', 'plan_sha256'}
    if not isinstance(plan, dict) or set(plan) != keys or plan['schema'] != 1 or plan['profile'] != PROFILE:
        raise BridgeError('Unsupported object creation plan.')
    if plan['kind'] not in KINDS:
        raise BridgeError('Unsupported creation kind.')
    if type(plan['save_project']) is not bool:
        raise BridgeError('save_project must be an explicit boolean.')
    object_name(plan['name'])
    initial = plan['initial']
    if not isinstance(initial, dict) or set(initial) != ({'source'} if plan['kind'] == 'litest_fb' else {'members'}):
        raise BridgeError('Unexpected initial-content fields.')
    initial_content(plan['kind'], initial.get('source'), initial.get('members'))
    unsigned = {k: v for k, v in plan.items() if k != 'plan_sha256'}
    if digest(unsigned) != plan['plan_sha256']:
        raise ConflictError('Object creation plan was changed; prepare a new plan.')
    _clean(plan['baseline'])


def _clean(snapshot):
    required = {'project', 'identity', 'native_hashes', 'registration_sha256', 'object_names',
                'dirty_documents', 'dialogs', 'cell_edits'}
    if not isinstance(snapshot, dict) or set(snapshot) != required:
        raise BridgeError('Incomplete object-creation baseline.')
    if any(snapshot[k] for k in ('dirty_documents', 'dialogs', 'cell_edits')):
        raise BridgeError('Creation requires a clean project with no dialogs or active cell edits.')
    if not isinstance(snapshot['native_hashes'], dict) or not isinstance(snapshot['object_names'], list):
        raise BridgeError('Invalid native/registration baseline.')
    identity = snapshot['identity']
    if (not isinstance(snapshot['project'],str) or not (Path(snapshot['project']).is_absolute() or PureWindowsPath(snapshot['project']).is_absolute())
            or not isinstance(identity,dict) or type(identity.get('pid')) is not int or identity['pid'] <= 0
            or not isinstance(snapshot['registration_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',snapshot['registration_sha256'])
            or any(not isinstance(v,str) or not v for v in snapshot['object_names'])):
        raise BridgeError('Invalid absolute project/process/registration identity.')
    for name, value in snapshot['native_hashes'].items():
        if (not isinstance(name,str) or not name or Path(name).is_absolute() or PureWindowsPath(name).is_absolute()
                or PureWindowsPath(name).drive or '..' in PureWindowsPath(name).parts
                or not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value)):
            raise BridgeError('Invalid relative native path/hash baseline.')


class ObjectCreationWorkflow:
    """A consumed create call cannot be replayed, even when its outcome is unknown."""
    def __init__(self, backend):
        self.backend = backend
        self.attempted = False

    def prepare(self, kind, name, *, source=None, members=None, save_project=False):
        if kind not in KINDS:
            raise BridgeError('Only LiteST FB and structure creation are supported.')
        object_name(name)
        content = initial_content(kind, source, members)
        if type(save_project) is not bool:
            raise BridgeError('save_project must be an explicit boolean.')
        baseline = self.backend.snapshot()
        _clean(baseline)
        self._available(baseline, name)
        plan = dict(schema=1, profile=PROFILE, kind=kind, name=name,
                    initial=content, save_project=save_project, baseline=copy.deepcopy(baseline))
        plan['plan_sha256'] = digest(plan)
        return dict(status='object_creation_ready', plan=plan, created=False, saved=False,
                    compile_outcome='not_run')

    @staticmethod
    def _available(snapshot, name):
        names = snapshot['object_names'] + [Path(p).stem for p in snapshot['native_hashes']]
        object_name(name, existing_names=names)

    def create(self, plan, *, experimental=False):
        if not experimental:
            raise BridgeError('Object creation requires explicit experimental=True.')
        if self.attempted:
            raise ConflictError('Creation receipt consumed; inspect current state before any new plan.')
        validate_plan(plan)
        baseline = self.backend.snapshot()
        _clean(baseline)
        self._available(baseline, plan['name'])
        if baseline != plan['baseline']:
            raise ConflictError('Project baseline changed after creation planning.')
        self.attempted = True
        stage = 'backup'
        backup = None
        submitted = False
        observed = None
        try:
            backup = self.backend.backup(plan)
            if not isinstance(backup, dict) or backup.get('verified') is not True or backup.get('unique') is not True:
                raise BridgeError('Verified non-overwriting creation backup required.')
            if self.backend.snapshot() != baseline:
                raise ConflictError('Project changed during creation backup.')
            stage = 'dialog_open'
            self.backend.open_dialog(plan['kind'])
            stage = 'dialog_configure'
            self.backend.configure_dialog(plan['kind'], plan['name'])
            self.backend.guard_before_submit(plan)
            stage = 'creation_submit'
            submitted = True
            self.backend.record(backup, dict(stage=stage, dispatch_may_have_occurred=True))
            self.backend.submit_dialog()
            stage = 'created_readback'
            observed = self.backend.observe(plan)
            if observed.get('created') is not True:
                raise BridgeError('Creation submission did not produce a uniquely identified native object.')
            self.backend.record(backup, dict(stage=stage, observed=observed))
            stage = 'initialize_and_save'
            self.backend.initialize(plan, observed, backup)
            if plan['save_project']:
                stage = 'project_registration_save'
                self.backend.save_project(plan, backup)
            stage = 'final_readback'
            observed = self.backend.observe(plan)
            self.backend.verify_existing(plan)
            required = ('created', 'saved', 'native_readback_verified', 'editor_readback_verified')
            if any(observed.get(key) is not True for key in required):
                raise BridgeError('New object save/native/editor verification incomplete.')
            registered = observed.get('registration_verified') is True
            result = dict(status='object_created_saved' if registered else 'object_created_pending_registration',
                          kind=plan['kind'], requested_name=plan['name'], object=observed,
                          backup=backup, compile_outcome='not_run', requires_user_compile=True,
                          requires_user_project_save=not registered, project_atomic=False)
            self.backend.record(backup, dict(stage='completed', result=result))
            return result
        except Exception as exc:
            # Read-only observation may itself fail; never infer absence from it.
            observation_error = None
            if submitted:
                try:
                    observed = self.backend.observe(plan)
                except Exception as read_error:
                    observation_error = str(read_error)
            result = dict(status='blocked', error_code='object_creation_partial_unknown' if submitted else 'object_creation_stopped',
                          stage=stage, error=str(exc), creation_dispatch_attempted=submitted,
                          target_may_have_changed=submitted, object=observed, observation_error=observation_error,
                          dialog_may_have_changed=stage != 'backup',
                          backup=backup, automatic_retry=False, automatic_rollback=False,
                          compile_outcome='not_run')
            if backup:
                try:
                    self.backend.record(backup, dict(stage='failed', result=result))
                except Exception as journal_error:
                    result['journal_error'] = str(journal_error)
            return result
