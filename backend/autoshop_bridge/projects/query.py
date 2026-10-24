"""Conservative disk-only declaration and lexical relationship queries.

This is a source navigator, not an IEC compiler. Every match carries evidence;
unresolved scopes and unsupported layouts remain visible in the result.
"""

import json
import re
from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.native import parse
from autoshop_bridge.projects.inventory import scan
from autoshop_bridge.workflows.source import bounded_int, clipped
from autoshop_bridge.storage import sha256

IDENT = re.compile(r"[^\W\d]\w*", re.UNICODE)
TOKEN = re.compile(r"[^\W\d]\w*|:=|=>|[.()\[\],;]|\S", re.UNICODE)
RELATIONS = (
    "definitions",
    "references",
    "type-users",
    "dependencies",
    "callers",
    "impact",
    "instances",
)


def masked_source(text):
    """Blank comments/quoted strings but retain line/column and token offsets."""
    chars = list(text)
    i, size = 0, len(text)
    while i < size:
        start = i
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = size if end < 0 else end
        elif text.startswith("(*", i):
            i, depth = i + 2, 1
            while i < size and depth:
                if text.startswith("(*", i):
                    depth, i = depth + 1, i + 2
                elif text.startswith("*)", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
        elif text[i] in "'\"":
            quote, i = text[i], i + 1
            while i < size:
                if text[i] == "$":
                    i += 2
                elif text[i] == quote:
                    if i + 1 < size and text[i + 1] == quote:
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
        else:
            i += 1
            continue
        for j in range(start, min(i, size)):
            if chars[j] not in "\r\n":
                chars[j] = " "
    return "".join(chars)


def source_chains(text):
    tokens = list(TOKEN.finditer(masked_source(text)))
    for index, token in enumerate(tokens):
        if not IDENT.fullmatch(token.group()) or (
            index and tokens[index - 1].group() == "."
        ):
            continue
        names, cursor = [token.group()], index + 1
        while cursor < len(tokens):
            if tokens[cursor].group() == "[":
                depth, cursor = 1, cursor + 1
                while cursor < len(tokens) and depth:
                    value = tokens[cursor].group()
                    depth += (value == "[") - (value == "]")
                    cursor += 1
                if depth:
                    break
            elif (
                tokens[cursor].group() == "."
                and cursor + 1 < len(tokens)
                and IDENT.fullmatch(tokens[cursor + 1].group())
            ):
                names.append(tokens[cursor + 1].group())
                cursor += 2
            else:
                break
        # Named call arguments are parameter labels, not variable references.
        if (
            len(names) == 1
            and cursor < len(tokens)
            and tokens[cursor].group() in (":=", "=>")
            and index
            and tokens[index - 1].group() in ("(", ",")
        ):
            continue
        start = token.start()
        line = text.count("\n", 0, start) + 1
        yield dict(
            names=names,
            line=line,
            column=start - text.rfind("\n", 0, start),
            call=cursor < len(tokens) and tokens[cursor].group() == "(",
        )


def build_index(project):
    inventory = scan(project, allow_readonly_tail=True)
    declarations, sources, unsupported = [], [], []
    for item in inventory["files"]:
        if item.get("status") != "parsed":
            unsupported.append(
                dict(
                    file=item.get("file"),
                    kind=item.get("kind"),
                    reason=item.get("error", item.get("reason", item.get("status"))),
                    **{
                        key: item[key]
                        for key in ("language", "language_evidence")
                        if key in item
                    },
                )
            )
            continue
        file, owner = item["file"], item["name"] or Path(item["file"]).stem
        raw = Path(item["path"]).read_bytes()
        if sha256(raw) != item["sha256"]:
            raise BridgeError("Project changed during indexing; scan again.")
        common = dict(file=file, owner=owner, native_sha256=item["sha256"])
        kind = item["kind"]
        if kind in ("st_program", "function_block", "function", "structure"):
            declarations.append(
                dict(
                    common,
                    symbol=owner,
                    name=owner,
                    kind=kind,
                    section="registration",
                    data_type=None,
                )
            )
        if kind in ("function_block", "function"):
            rows, section = item["variables"]["variables"], "variables"
        elif kind == "structure":
            rows, section = item["structure"]["members"], "members"
        elif kind == "global_variables":
            rows, section = item["table"]["rows"], "globals"
        elif kind == "function_block_instances":
            rows, section = item["instances"]["instances"], "instances"
        else:
            rows, section = [], None
        for row in rows:
            declarations.append(
                dict(
                    common,
                    symbol=owner + "." + row["name"],
                    name=row["name"],
                    kind=(
                        "member"
                        if kind == "structure"
                        else "function_block_instance"
                        if section == "instances"
                        else "variable"
                    ),
                    section=section,
                    data_type=row.get("data_type"),
                    type_reference=row.get("type_text_raw") or row.get("data_type"),
                    type_code=row.get("type_code"),
                    category=row.get("category"),
                    comment=row.get("comment"),
                )
            )
        if kind in ("st_program", "function_block", "function"):
            sources.append(
                dict(
                    common,
                    text=parse(raw, Path(file).suffix.lower()[1:]).source.decode(
                        "utf-8"
                    ),
                )
            )
    stamp = dict(
        registration=inventory["registration_source"]["sha256"],
        files=sorted((x.get("file"), x.get("sha256")) for x in inventory["files"]),
    )
    return (
        inventory,
        declarations,
        sources,
        unsupported,
        sha256(json.dumps(stamp, sort_keys=True).encode()),
    )


def code_query(project, symbol, relation="definitions", limit=20, offset=0):
    validate_query(symbol, relation, limit, offset)
    return query_index(build_index(project), symbol, relation, limit, offset)


def validate_query(symbol, relation, limit, offset):
    if (
        not isinstance(symbol, str)
        or len(symbol) > 512
        or not all(IDENT.fullmatch(x) for x in symbol.split("."))
    ):
        raise BridgeError(
            "Symbol must be a dot-qualified identifier, not an expression."
        )
    if relation not in RELATIONS:
        raise BridgeError("Unsupported code relation.")
    bounded_int(limit, 1, 100, "limit")
    bounded_int(offset, 0, 100000, "offset")


def query_index(index, symbol, relation="definitions", limit=20, offset=0):
    validate_query(symbol, relation, limit, offset)
    inventory, declarations, sources, unsupported, digest = index
    key = symbol.casefold()
    exact = [d for d in declarations if d["symbol"].casefold() == key]
    definitions = exact or [d for d in declarations if d["name"].casefold() == key]
    results = []
    if relation == "definitions":
        results = [dict(d, evidence="parsed_declaration") for d in definitions]
    elif relation == "instances":
        results = [
            dict(d, evidence="parsed_instance_record")
            for d in declarations
            if d["section"] == "instances"
            and (d.get("type_reference") or "").casefold() == key
        ]
    elif relation == "type-users":
        results = [
            dict(d, evidence="parsed_type_reference")
            for d in declarations
            if (d.get("type_reference") or "").casefold() == key
        ]
    elif relation == "dependencies":
        results = [
            dict(d, evidence="parsed_type_reference")
            for d in declarations
            if d["owner"].casefold() == key and d.get("type_reference")
        ]
    else:
        if relation == "impact":
            results.extend(
                dict(d, evidence="parsed_type_reference")
                for d in declarations
                if (d.get("type_reference") or "").casefold() == key
            )
        for source in sources:
            local = [
                d
                for d in declarations
                if d["owner"] == source["owner"] and d["section"] == "variables"
            ]
            globals_ = [
                d for d in declarations if d["section"] in ("globals", "instances")
            ]
            lines = source["text"].split("\n")
            for occurrence in source_chains(source["text"]):
                names = occurrence["names"]
                root = names[0].casefold()
                bindings = [d for d in local if d["name"].casefold() == root]
                if not bindings:
                    bindings = [d for d in globals_ if d["name"].casefold() == root]
                targets = {
                    ".".join(names).casefold(),
                    source["owner"].casefold() + "." + root,
                }
                evidence = "lexical_candidate"
                if len(bindings) == 1:
                    binding = bindings[0]
                    targets.add(binding["symbol"].casefold())
                    type_name = binding.get("type_reference")
                    # Resolve structure member chains against declared member types.
                    if type_name and len(names) > 1:
                        for member in names[1:]:
                            qualified = type_name + "." + member
                            targets.add(qualified.casefold())
                            declared = [
                                d
                                for d in declarations
                                if d["symbol"].casefold() == qualified.casefold()
                                and d["section"] in ("members", "variables")
                            ]
                            if len(declared) != 1:
                                break
                            type_name = declared[0].get("type_reference")
                            if not type_name:
                                break
                    if len(names) == 1:
                        evidence = "scoped_identifier"
                    if occurrence["call"] and len(names) == 1 and type_name:
                        targets.add(type_name.casefold())
                if relation == "callers" and not occurrence["call"]:
                    continue
                if key not in targets:
                    continue
                results.append(
                    dict(
                        file=source["file"],
                        owner=source["owner"],
                        native_sha256=source["native_sha256"],
                        section="source",
                        line=occurrence["line"],
                        column=occurrence["column"],
                        expression=".".join(names),
                        evidence=evidence,
                        relation="call_candidate"
                        if occurrence["call"]
                        else "reference",
                        snippet=clipped(lines[occurrence["line"] - 1].rstrip("\r")),
                    )
                )
    return dict(
        status="code_query",
        schema=1,
        source="disk",
        read_only=True,
        relation=relation,
        symbol=symbol,
        project=inventory["project"],
        index_sha256=digest,
        registration_source=inventory["registration_source"],
        coverage="partial",
        total_matches=len(results),
        offset=offset,
        limit=limit,
        next_offset=offset + limit if offset + limit < len(results) else None,
        matches=results[offset : offset + limit],
        unsupported_count=len(unsupported),
        unsupported_program_objects=[
            u
            for u in unsupported
            if u["kind"]
            in (
                "function_block",
                "st_program",
                "structure",
                "global_variables",
                "system_variables",
                "function_block_instances",
                "function_instances_pending",
                "function_pending",
                "function",
                "ladder_pending",
            )
            or Path(u.get("file") or "").suffix.lower() in (".fbi", ".fci")
        ][:10],
        limitations=[
            "Disk snapshot excludes unsaved editor buffers.",
            "Lexical/call candidates are not compiler-resolved semantic references.",
            "Only parsed declarations and direct type/member relationships are resolved.",
            "Supported FBI record segments are read-only; surrounding archive metadata is opaque.",
            "ST-local declaration scopes and unsupported instance layouts are not yet parsed.",
            "Impact is a direct candidate list, not a complete transitive proof.",
        ],
    )


def code_context(project, symbol, max_items=20):
    """One disk index, a shared bounded budget for an AI's first inspection."""
    bounded_int(max_items, 1, 100, "max_items")
    validate_query(symbol, "definitions", 1, 0)
    index = build_index(project)
    relations = (
        "definitions",
        "dependencies",
        "instances",
        "callers",
        "references",
        "type-users",
    )
    per_relation = (max_items + len(relations) - 1) // len(relations)
    sections, remaining, common = {}, max_items, None
    for relation in relations:
        result = query_index(
            index, symbol, relation, max(1, min(per_relation, remaining))
        )
        if common is None:
            common = {
                key: result[key]
                for key in (
                    "schema",
                    "project",
                    "source",
                    "read_only",
                    "symbol",
                    "index_sha256",
                    "registration_source",
                    "coverage",
                    "limitations",
                    "unsupported_count",
                    "unsupported_program_objects",
                )
            }
        matches = result["matches"][:remaining]
        sections[relation] = dict(
            total_matches=result["total_matches"],
            matches=matches,
            next_offset=len(matches)
            if len(matches) < result["total_matches"]
            else None,
        )
        remaining -= len(matches)
    return dict(
        common,
        status="code_context",
        max_items=max_items,
        returned_items=max_items - remaining,
        sections=sections,
        complete=False,
        next_action="Use code-query with relation and next_offset for more items.",
    )
