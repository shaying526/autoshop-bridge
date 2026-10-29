"""Private experimental registration capture/live observation, never implicit UI.

Only the listed object categories are mapped to closed-HCP identities. Other
native/configuration objects remain outside tree type coverage; all registered
file presence/content is frozen by the receipt. No project close/open, menu,
compile, save, input or PLC action is dispatched by this module.
"""

import copy
from pathlib import Path

from autoshop_bridge.projects import inventory
from autoshop_bridge.projects import registration_evidence as receipts
from autoshop_bridge.storage import write_json_new

CATEGORY_KINDS = {
    "程序块": {"st_program", "ladder_program"},
    "功能块(FB)": {"function_block"},
    "功能块": {"function_block"},
    "结构体": {"structure"},
    "数据类型": {"structure"},
    "全局变量表": {"global_variables"},
    "软元件表": {"global_variables"},
    "功能块实例": {"function_block_instances"},
}


def _require(condition, code, message, context=None):
    if not condition:
        raise receipts.RegistrationEvidenceError(code, message, context=context)


def normalize_tree_inventory(raw, receipt, *, category_kinds=None):
    """Map complete native tree items in supported categories, without guessing.

    Unknown nodes outside supported categories are reported, not treated as
    editable objects or evidence of complete configuration-object identity.
    Within a supported category an unknown/misclassified object fails closed.
    """
    categories = CATEGORY_KINDS if category_kinds is None else category_kinds
    _require(isinstance(raw, dict) and raw.get("profile") == "native-tree-items-msaa-v1"
             and raw.get("complete") is True and raw.get("includes_collapsed_items") is True,
             "registration_needs_refresh", "A complete native tree inventory is required.")
    nodes = raw.get("nodes")
    _require(isinstance(nodes, list) and len(nodes) <= 10000
             and raw.get("node_count") == len(nodes) == raw.get("tree_count_before") == raw.get("tree_count_after"),
             "registration_needs_refresh", "Tree enumeration counts are incomplete or unstable.")
    expected = receipt["tree_objects"]
    objects, category_nodes, unclassified = [], {}, []
    object_nodes, global_containers, excluded_nodes = {}, set(), set()
    internal_nodes, excluded_global_nodes, caption_aliases = [], [], []

    def matches_for(name, kinds):
        # AutoShop's observed tree spells SBR_Tray while its closed HCP keeps
        # SBR_TRAY. Require a unique case-insensitive identity within category;
        # retain both spellings instead of changing the frozen registration.
        return [item for item in expected if item["caption"].casefold() == name.casefold()
                and item["kind"] in kinds]

    def record_object(index, name, matches):
        _require(len(matches) == 1, "registration_stale",
                 "A live object in a supported category is new, renamed or ambiguous: {}.".format(name),
                 dict(evidence_source="live_project_tree", differences=[dict(object=name,
                      field="unique_captured_match_count", before=1, after=len(matches))], node_index=index))
        matched = copy.deepcopy(matches[0])
        objects.append(matched)
        object_nodes[index] = matched
        if name != matched["caption"]:
            caption_aliases.append(dict(index=index, live_caption=name,
                                        registered_caption=matched["caption"],
                                        rule="unique_casefold_within_category"))

    for index, node in enumerate(nodes):
        _require(isinstance(node, dict) and node.get("index") == index and node.get("role") == 36
                 and isinstance(node.get("parent"), int) and -1 <= node["parent"] < index
                 and isinstance(node.get("depth"), int) and 0 <= node["depth"] <= 32
                 and isinstance(node.get("name"), str) and bool(node["name"]),
                 "registration_needs_refresh", "Tree node identity/hierarchy is invalid.")
        parent = node["parent"]
        _require(node["depth"] == (0 if parent == -1 else nodes[parent]["depth"] + 1),
                 "registration_needs_refresh", "Tree node depth and parent disagree.")
        name = node["name"]
        ancestor = parent
        owner, excluded_ancestor = None, None
        while ancestor != -1:
            if ancestor in object_nodes:
                owner = ancestor
                break
            if ancestor in excluded_nodes:
                excluded_ancestor = ancestor
                break
            ancestor = nodes[ancestor]["parent"]
        if owner is not None:
            _require(object_nodes[owner]["kind"] in ("st_program", "ladder_program", "function_block"),
                     "registration_needs_refresh", "Internal tree layout is unsupported for this object kind.")
            internal_nodes.append(dict(index=index, parent=parent, name=name,
                                       owner_index=owner, scope="pou_internal_not_project_object"))
            continue
        if excluded_ancestor is not None:
            unclassified.append(dict(index=index, parent=parent, name=name,
                                     excluded_ancestor=excluded_ancestor))
            continue
        if name == "全局变量" and (parent == -1 or nodes[parent]["parent"] == -1):
            global_containers.add(index)
            continue
        if parent in global_containers:
            # In the observed V4.11.0.5 hierarchy GVT/FBI are direct objects,
            # including the FBI whose name equals the old category label.
            mapped = matches_for(name, {"global_variables", "function_block_instances"})
            if mapped:
                record_object(index, name, mapped)
                continue
            if name in ("枚举", "软元件表"):
                excluded_nodes.add(index)
                excluded_global_nodes.append(dict(index=index, parent=parent, name=name,
                                                  scope="unmapped_global_definition"))
                continue
            _require(name in ("结构体", "数据类型"), "registration_stale",
                     "Unmapped object in the observed global-variable container: {}.".format(name))
        if name in categories:
            _require(name not in category_nodes, "registration_needs_refresh", "Duplicate supported category name.")
            category_nodes[name] = index
            continue
        ancestor = parent
        while ancestor != -1 and nodes[ancestor]["name"] not in categories:
            ancestor = nodes[ancestor]["parent"]
        if ancestor == -1:
            unclassified.append(dict(index=index, parent=parent, name=name))
            continue
        kinds = categories[nodes[ancestor]["name"]]
        record_object(index, name, matches_for(name, kinds))
    objects.sort(key=lambda item: (item["kind"], item["caption"]))
    _require(objects == expected, "registration_stale", "Supported project-object set differs from closed HCP.",
             receipts.comparison("live_project_tree", {r["caption"]: r for r in expected},
                                 {r["caption"]: r for r in objects}))
    return dict(tree_objects=objects, tree_inventory_complete=True,
                tree_scope="mapped_editable_object_categories_only",
                observed_categories=sorted(category_nodes), unclassified_tree_nodes=unclassified,
                internal_tree_nodes=internal_nodes, excluded_global_nodes=excluded_global_nodes,
                caption_aliases=caption_aliases,
                excluded_registration_files=[row["file"] for row in receipt["registration_rows"]
                                             if row["file"] and (receipts.TREE_KINDS.get(Path(row["file"]).suffix.lower())
                                                                  not in set().union(*categories.values()))],
                raw_tree=copy.deepcopy(raw), atomic_snapshot=False)


def capture_registration(project, program, output, *, pid=None, driver=None):
    """CLI-ready capture for an already closed, clean exact AutoShop process.

    output is created exclusively; existing files are never replaced. The real
    driver is constructed only when this explicit function is invoked.
    """
    hcp = inventory.select_project(Path(project))
    if driver is None:
        from autoshop_bridge.windows.project_lifecycle import WindowsProjectDriver
        driver = WindowsProjectDriver(hcp, pid)
    before = driver.snapshot()
    _require(not before.get("duplicates"), "registration_identity_mismatch", "Duplicate project sessions exist.")
    receipt = receipts.capture_closed_target(hcp, program, before)
    _require(driver.snapshot() == before, "registration_needs_refresh", "Session changed during direct-HCP capture.")
    write_json_new(Path(output), receipt)
    return dict(status="experimental_registration_captured", output=str(Path(output).resolve()),
                receipt_sha256=receipt["receipt_sha256"], scope=receipt["scope"],
                structural_mutation_authorized=False, ide_validation="pending")


class RegistrationObserver:
    """Read-only callable for session.connect's explicit experimental branch."""

    def __init__(self, receipt, *, driver=None):
        self.receipt = copy.deepcopy(receipt)
        self.driver = driver

    def _driver(self):
        if self.driver is None:
            from autoshop_bridge.windows.project_lifecycle import WindowsProjectDriver
            self.driver = WindowsProjectDriver(Path(self.receipt["project_file"]),
                                               self.receipt["closed_identity"]["pid"])
        return self.driver

    @staticmethod
    def _tree(adapter):
        trees = []
        for child in adapter.children(adapter.main):
            if adapter.class_name(child) != "SysTreeView32":
                continue
            ancestor = adapter.user.GetParent(child)
            while ancestor and ancestor != adapter.main:
                if adapter.text(ancestor) == "工程管理":
                    trees.append(child)
                    break
                ancestor = adapter.user.GetParent(ancestor)
        _require(len(trees) == 1, "registration_needs_refresh", "Exactly one project-management tree is required.")
        return trees[0]

    def _observe(self, adapter, *, require_document):
        driver = self._driver()
        before = driver.snapshot()
        hcp = Path(self.receipt["project_file"])
        identity = receipts._observation(before, hcp, "opened")
        _require(identity == self.receipt["closed_identity"] and not before.get("duplicates")
                 and adapter.pid == identity["pid"] and adapter.main == identity["main"]
                 and adapter.project == str(hcp.parent) and adapter.program == self.receipt["program"],
                 "registration_identity_mismatch", "Exact target/process/project identity differs.",
                 receipts.comparison("live_process", {"process": self.receipt["closed_identity"]},
                                     {"process": identity}))
        kind = receipts.TREE_KINDS.get(Path(self.receipt["target"]["file"]).suffix.lower())
        _require(kind in receipts.LIVE_TREE_KINDS, "registration_scope_denied", "Target tree category has no observed mapping profile.")
        adapter.validate_main()
        tree = self._tree(adapter)
        raw = adapter.accessible("tree_inventory", tree)
        mapped = normalize_tree_inventory(raw, self.receipt)
        # The tree supplies category/caption; the independently attached open
        # document must still match the frozen native body and complete table.
        if require_document:
            adapter.locate_editor(required=True)
            adapter.validate_handles()
            from autoshop_bridge.windows.session import assert_clean_native
            target = Path(self.receipt["target_path"])
            assert_clean_native(adapter, target, inventory.bounded_read(target))
        second = adapter.accessible("tree_inventory", tree)
        _require(second == raw and driver.snapshot() == before,
                 "registration_needs_refresh", "Tree or session changed during target observation.")
        observed = copy.deepcopy(before)
        observed.update(mapped)
        observed.update(target_identity_source="live_project_tree",
                        target=dict(caption=self.receipt["target"]["caption"], kind=kind),
                        target_document_verified=require_document)
        return observed

    def __call__(self, adapter):
        return self._observe(adapter, require_document=True)

    def navigation_guard(self, adapter):
        """Prove frozen target/tree/files before an explicitly requested open."""
        receipts.receipt_identity(Path(self.receipt["project_file"]), self.receipt["program"],
                                  self.receipt, adapter.pid)
        observation = self._observe(adapter, require_document=False)
        return receipts.verify_target_receipt(Path(self.receipt["project_file"]),
                                              self.receipt["program"], self.receipt,
                                              observation, operation="target_read")

    def verify(self, adapter, *, operation="target_read"):
        observation = self(adapter)
        return receipts.verify_target_receipt(Path(self.receipt["project_file"]),
                                              self.receipt["program"], self.receipt,
                                              observation, operation=operation)

    def mutation_guard(self, adapter):
        """Call immediately before the first content mutation of a clean target.

        This does not save, permit variable/type additions or authorize a second
        operation after native bytes change. A caller owns the existing backup,
        exact buffer/variable baseline, dispatch and post-save readback guards.
        """
        return self.verify(adapter, operation="target_content")


def bind_registration(receipt, adapter, *, driver=None):
    """Purely read/bind one current target; no menu navigation or implicit open."""
    observer = RegistrationObserver(receipt, driver=driver)
    return observer.verify(adapter, operation="target_read")
