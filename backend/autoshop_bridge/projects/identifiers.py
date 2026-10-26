"""Evidence-bounded checks for new names, never native-record recognition.

No project, installation, IDE, or PLC access occurs here. A passing assessment
means only that the supplied checks found no conflict; AutoShop remains the
authority for acceptance. See docs/IDENTIFIER_RULES.md for evidence and limits.
"""

from autoshop_bridge.errors import BridgeError


KNOWN_KEYWORDS = frozenset({"ARRAY", "TRUE", "FALSE", "ON", "OFF", "NULL"})
KNOWN_STANDARD_TYPES = frozenset(
    {"BOOL", "INT", "DINT", "REAL", "STRING", "IP", "BYTE"}
)
# Narrow reference evidence, NOT complete or automatically applicable catalogs.
REFERENCE_INSTRUCTIONS = frozenset({"BSET", "DBSET"})
REFERENCE_SOFT_ELEMENTS = frozenset({"B1"})
REFERENCE_MANUAL = "AutoShopH530.chm"
REFERENCE_MANUAL_SHA256 = (
    "ca3725656721b6a36ca06a89e175537517820de68f3b70abbb098b186774d3c3"
)
TOOL_MAX_UTF8_BYTES = 63


def _names(values, label):
    """Validate explicit context instead of silently omitting broken evidence."""
    if isinstance(values, (str, bytes)):
        raise BridgeError("Identifier context {} requires a collection of names.".format(label))
    try:
        names = tuple(values)
    except TypeError as exc:
        raise BridgeError("Identifier context {} requires a collection of names.".format(label)) from exc
    if any(not isinstance(name, str) or not name for name in names):
        raise BridgeError("Identifier context {} requires nonempty string names.".format(label))
    return names


def assess_identifier(
    name, *, existing_names=(), project_names=(), instruction_names=(),
    soft_element_names=()
):
    """Return rejected or needs_ide_validation with reasons and evidence scope.

    Context names must already be selected for the target scope/model/version.
    Matching uses casefold as a conservative backend policy, not a claim about
    the IDE's undocumented case comparison. No complete reserved set is implied.
    """
    contexts = (
        ("local_duplicate", "existing_names", _names(existing_names, "existing_names")),
        ("project_name_conflict", "project_names", _names(project_names, "project_names")),
        ("instruction_name_conflict", "instruction_names", _names(instruction_names, "instruction_names")),
        ("soft_element_name_conflict", "soft_element_names", _names(soft_element_names, "soft_element_names")),
    )
    issues, candidates = [], []

    def issue(code, scope, message, **details):
        issues.append(dict(code=code, evidence_scope=scope, message=message, **details))

    if not isinstance(name, str) or not name:
        issue("invalid_identifier", "naming_rule", "A new name must be a nonempty string.")
    elif (
        not name[0].isalpha()
        or not name.isidentifier()
        or any(not (char == "_" or char.isalpha() or char.isdecimal()) for char in name)
    ):
        issue(
            "invalid_identifier", "naming_rule",
            "A new name requires letters/digits/Chinese characters/underscores and a letter first.",
        )
    else:
        if len(name.encode("utf-8")) > TOOL_MAX_UTF8_BYTES:
            issue(
                "identifier_tool_length_limit", "backend_policy",
                "A new name exceeds the backend's 63 UTF-8 byte limit.",
            )
        if name.upper() in KNOWN_KEYWORDS:
            issue("reserved_keyword", "documented_naming_rule", "A new name matches a documented keyword.")
        if name.upper() in KNOWN_STANDARD_TYPES:
            issue("standard_type_name", "documented_naming_rule", "A new name matches a documented standard data type.")
        for code, label, names in contexts:
            matches = sorted({value for value in names if value.casefold() == name.casefold()})
            if matches:
                issue(
                    code, "supplied_context", "A new name conflicts with explicit {} context.".format(label),
                    matches=matches, comparison="casefold_backend_policy",
                )
        for code, names, label, stream in (
            ("instruction_name_candidate", REFERENCE_INSTRUCTIONS, "instruction_names", "/T2025082800194.html"),
            ("soft_element_name_candidate", REFERENCE_SOFT_ELEMENTS, "soft_element_names", "/T2025082800052.html"),
        ):
            reference = sorted(value for value in names if value.casefold() == name.casefold())
            supplied = next(values for _, key, values in contexts if key == label)
            if reference and not any(value.casefold() == name.casefold() for value in supplied):
                candidates.append(dict(
                    code=code, matches=reference, evidence_scope="reference_manual_only",
                    source=REFERENCE_MANUAL, stream=stream,
                    comparison="casefold_backend_policy", applicability="not_confirmed_for_target",
                ))
    return dict(
        name=name if isinstance(name, str) else None,
        status="rejected" if issues else "needs_ide_validation",
        issues=issues, candidates=candidates,
        context_counts={label: len(names) for _, label, names in contexts},
        unverified=[
            "complete_instruction_catalog", "complete_soft_element_and_constant_forms",
            "context_completeness_and_freshness", "ide_acceptance",
        ],
    )


def require_new_identifier(
    name, *, existing_names=(), project_names=(), instruction_names=(),
    soft_element_names=()
):
    """Raise BridgeError for known rejection; otherwise return the assessment."""
    result = assess_identifier(
        name, existing_names=existing_names, project_names=project_names,
        instruction_names=instruction_names, soft_element_names=soft_element_names,
    )
    if result["status"] == "rejected":
        reasons = "; ".join("{}: {}".format(item["code"], item["message"]) for item in result["issues"])
        raise BridgeError("New identifier {!r} rejected: {}".format(name, reasons))
    return result


def precheck_addition_names(document):
    """Apply the narrow backend guard to add operations, before IDE access.

    Reference-manual instruction/soft-element examples are advisory. They are
    not automatically promoted into the current project's reserved namespace.
    This does not replace the caller's schema/unique-target checks.
    Sets of existing declarations remain readable and editable by exact name.
    """
    if not isinstance(document, dict) or not isinstance(document.get("operations"), list):
        return
    for operation in document["operations"]:
        if isinstance(operation, dict) and operation.get("op") == "add":
            require_new_identifier(operation.get("name"))
