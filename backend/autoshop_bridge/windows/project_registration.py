"""Explicit project-baseline observation; no implicit project lifecycle or save."""

import base64
import copy
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.projects import inventory, registration_baseline as baselines
from autoshop_bridge.projects import registration_evidence as evidence
from autoshop_bridge.storage import write_json_new, sha256
from autoshop_bridge.windows.registration_observer import RegistrationObserver, normalize_tree_inventory, CATEGORY_KINDS


def capture_project_registration(project, pid, output, *, driver=None):
    from autoshop_bridge.windows.project_lifecycle import WindowsProjectDriver
    hcp = inventory.select_project(Path(project))
    output = Path(output).resolve()
    if hcp.parent == output or hcp.parent in output.parents:
        raise BridgeError('Project registration baseline must be outside the project.')
    driver = driver or WindowsProjectDriver(hcp, pid)
    state = driver.snapshot()
    receipt = baselines.capture(hcp, state)
    if driver.snapshot() != state:
        raise BridgeError('Session changed during project registration capture.')
    write_json_new(output, receipt)
    return dict(status='project_registration_baseline_captured', output=str(output),
                scope=receipt['scope'], receipt_sha256=receipt['receipt_sha256'],
                lifecycle_dispatched=False, mutation_authorized=False)


class ProjectRegistrationScope:
    """One explicit command, with preflight file proof and fresh tree checks.

    This is a registration source, not a replacement for a mutation's native,
    buffer, backup or concurrency checks. Baselines expire after saved edits.
    """
    def __init__(self, receipt, project=None, pid=None, *, driver=None, adapter=None, allowed_targets=()):
        self.receipt = baselines.load(receipt)
        self.hcp = Path(self.receipt['project_file'])
        if project is not None and inventory.select_project(Path(project)) != self.hcp:
            raise BridgeError('Project registration baseline belongs to a different project.')
        if pid is not None and pid != self.receipt['closed_identity']['pid']:
            raise BridgeError('Project registration baseline belongs to a different process.')
        from autoshop_bridge.windows.project_lifecycle import WindowsProjectDriver
        from autoshop_bridge.windows.session import WindowsSession
        self.driver = driver or WindowsProjectDriver(self.hcp, self.receipt['closed_identity']['pid'])
        self.adapter = adapter or WindowsSession(self.hcp.parent, '__project_registration__', self.receipt['closed_identity']['pid'])
        self.raw = base64.b64decode(self.receipt['registration_raw_b64'])
        self.addition = None
        self.dialog = None
        self.active = False
        self.verified_reference_changes = {}
        self.allowed_targets = set(allowed_targets)
        if not self.allowed_targets <= set(self.receipt['native_hashes']):
            raise BridgeError('Registration mutation target is outside the captured native set.')

    def _protected_files(self):
        """Own targets retain their operation guards; all other files stay frozen."""
        hashes = evidence._native_hashes(self.hcp.parent, self.receipt['registration_rows'])
        expected = dict(self.receipt['native_hashes'])
        expected.update(self.verified_reference_changes)
        if self.addition is not None:
            name = self.addition['caption'] + ('.FB' if self.addition['kind'] == 'function_block' else '.stru')
            new = [key for key in hashes if key.casefold() == name.casefold() and key not in expected]
            if len(new) != 1:
                raise BridgeError('Exactly one planned new native file is required.')
            del hashes[new[0]]
        for key in self.allowed_targets:
            hashes.pop(key, None); expected.pop(key, None)
        if hashes != expected:
            raise BridgeError('Protected native files changed during registration command.')
        states = evidence._registered_file_states(self.hcp.parent, self.receipt['registration_rows'])
        old = self.receipt['registered_file_states']
        if any(states[name] != (dict(state='present', sha256=self.verified_reference_changes[name])
                               if name in self.verified_reference_changes else value)
               for name, value in old.items() if name not in self.allowed_targets):
            raise BridgeError('Protected registered file presence/content changed during registration command.')
        try:
            direct = inventory._read_hcp(self.hcp)
        except PermissionError:
            return
        if direct == self.raw:
            return
        if self.addition is None:
            raise BridgeError('Direct registration changed during command.')
        old_root, new_root = inventory.registration(self.raw), inventory.registration(direct)
        old_nodes = {node.get('id'): ET.tostring(node, encoding='unicode') for node in old_root.findall('file')}
        rows = evidence._rows(direct, self.hcp.parent)  # Also reject duplicate ids/paths.
        new_nodes = {node.get('id'): ET.tostring(node, encoding='unicode') for node in new_root.findall('file')}
        delta = [row for row in rows if row['id'] not in old_nodes]
        suffix = '.fb' if self.addition['kind'] == 'function_block' else '.stru'
        expected_name = self.addition['caption']
        if (not all(new_nodes.get(key) == value for key, value in old_nodes.items())
                or len(delta) != 1 or delta[0]['caption'] != expected_name
                or Path(delta[0]['file']).suffix.lower() != suffix
                or Path(delta[0]['file']).stem != expected_name
                or len(inventory.member_path(delta[0]['file'])) != 1):
            raise BridgeError('Direct registration changed outside the single planned object; recapture after normal closure.')
        delta_id = delta[0]['id']
        new_root.remove(next(node for node in new_root.findall('file') if node.get('id') == delta_id))
        def shape(node):
            # Ignore indentation only, never meaningful leaf text/attributes.
            text = None if len(node) and not (node.text or '').strip() else node.text
            tail = node.tail if (node.tail or '').strip() else None
            return node.tag, node.attrib, text, tail, [shape(child) for child in node]
        if shape(new_root) != shape(old_root):
            raise BridgeError('Direct HCP metadata changed outside the planned registration; close and recapture.')

    def _session(self):
        state = self.driver.snapshot()
        if (state['identity'] != self.receipt['closed_identity'] or state['state'] != 'opened'
                or state['duplicates'] or state['project_file'] != str(self.hcp)):
            raise BridgeError('Project registration process/project identity changed.')
        if self.dialog is not None:
            if state['dialogs'] != self.dialog:
                raise BridgeError('Known creation dialog identity changed.')
        elif not state['enabled'] or state['dialogs']:
            raise BridgeError('Project registration encountered an unknown modal dialog.')
        allowed_documents = {Path(name).stem for name in self.allowed_targets}
        allowed_documents.update(row['caption'] for row in self.receipt['registration_rows']
                                 if row['file'] and '/'.join(inventory.member_path(row['file'])) in self.allowed_targets)
        if self.addition is not None:
            allowed_documents.add(self.addition['caption'])
        for item in [*state['dirty'], *state['cell_edits']]:
            document = item.get('document') if isinstance(item, dict) else item
            if not isinstance(document, str) or document.rstrip().rstrip('*').rstrip() not in allowed_documents:
                raise BridgeError('Unrelated dirty document or active cell appeared during registration command.')
        return state

    def accept_verified_result(self, result):
        """Only the existing rename writer's exact verified reference hashes."""
        if result.get('reference_updates') and result.get('references_updated_by') != 'AutoShop':
            raise BridgeError('Reference changes require the existing verified AutoShop writer result.')
        for row in result.get('reference_updates', []):
            path = Path(row['file']).resolve()
            if self.hcp.parent not in path.parents:
                raise BridgeError('Reference update leaves the qualified project.')
            name = path.relative_to(self.hcp.parent).as_posix()
            if (path.suffix.lower() not in ('.st', '.fb', '.fc')
                    or self.receipt['native_hashes'].get(name) != row.get('before_sha256')
                    or row.get('after_sha256') != sha256(inventory.bounded_read(path))):
                raise BridgeError('Verified reference update differs from the registration baseline/result.')
            self.verified_reference_changes[name] = row['after_sha256']

    def observe(self):
        before = self._session()
        if self.dialog is not None:
            return None  # Tree was frozen immediately before this exact dialog.
        expected = copy.deepcopy(self.receipt)
        # FC has an independently observed category in this project-level
        # protocol. Do not expand the old target-content receipt's scope.
        expected['tree_objects'].extend(dict(caption=row['caption'], kind='function')
            for row in self.receipt['registration_rows'] if row['file'] and Path(row['file']).suffix.lower() == '.fc')
        if self.addition is not None:
            expected['tree_objects'].append(dict(self.addition))
        expected['tree_objects'].sort(key=lambda row: (row['kind'], row['caption']))
        a = self.adapter
        a.validate_main()
        mapped = normalize_tree_inventory(a.accessible('tree_inventory', RegistrationObserver._tree(a)), expected,
                                          category_kinds=dict(CATEGORY_KINDS, **{'函数(FC)': {'function'}}))
        after = self._session()
        left, right = dict(before), dict(after)
        if self.addition is not None:
            # AutoShop opens its newly created empty document asynchronously.
            # Target focus/title is checked by the content adapter later; all
            # clean/process/modal state and the complete tree remain strict.
            for key in ('title', 'documents'):
                left.pop(key, None); right.pop(key, None)
        if right != left:
            raise BridgeError('Project tree/session changed during registration observation.')
        return mapped

    def get_registration(self, hcp):
        if not self.active or Path(hcp) != self.hcp:
            raise BridgeError('Scoped registration cannot be used outside its exact project/command.')
        self.observe()
        self._protected_files()
        return self.raw, dict(path=str(self.hcp), kind='closed_hcp_live_tree_verified',
            possibly_stale=False, current_hcp_verified=False,
            registration_mapping_scope='captured_objects_only',
            persistent_registration_pending=self.addition is not None,
            receipt_sha256=self.receipt['receipt_sha256'],
            opaque_hcpp_is_authority=False)

    @contextmanager
    def known_creation_dialog(self, hwnd):
        if self.dialog is not None:
            raise BridgeError('Nested creation dialog scope is unsupported.')
        actual = self.driver.snapshot()['dialogs']
        if len(actual) != 1 or actual[0]['hwnd'] != hwnd:
            raise BridgeError('Exact configured creation dialog is required.')
        self.dialog = actual
        try:
            yield
        finally:
            self.dialog = None

    def mark_creation(self, kind, name):
        if self.addition is not None or kind not in ('litest_fb', 'structure'):
            raise BridgeError('Only one planned object may be added in a registration command.')
        self.addition = dict(caption=name, kind='function_block' if kind == 'litest_fb' else 'structure')

    @contextmanager
    def entered(self):
        state = self._session()
        if state['dirty'] or state['cell_edits']:
            raise BridgeError('Project registration requires a clean command starting point.')
        baselines.verify_files(self.receipt)
        self.observe()
        baselines.verify_files(self.receipt)
        self.active = True
        try:
            with baselines.scoped(self):
                yield self
                # A successful command cannot escape without a final complete
                # tree and non-target proof, including files changed late.
                self.observe()
                self._protected_files()
        finally:
            self.active = False
