"""Rename existing structure members and observed named initializer keys.

Only string spans are replaced. No address, type, order, opaque field or source
reference is changed. A declaration rename is not a business-reference check.
"""
from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import fb, tables
from autoshop_bridge.formats.structure import comment_initializer


def structure(raw, renames):
    before = tables.parse(raw, "stru")
    if not isinstance(renames, list) or not 1 <= len(renames) <= 4096:
        raise BridgeError("Expected 1..4096 explicit old/new member names.")
    by_name = {r.name: r for r in before.rows}
    mapping = {}
    for item in renames:
        if (not isinstance(item, dict) or set(item) != {"old", "new"}
                or not isinstance(item["old"], str) or item["old"] not in by_name
                or not tables.identifier(item["new"]) or item["old"] in mapping):
            raise BridgeError("Member rename requires a unique exact old name and a valid new identifier.")
        mapping[item["old"]] = item["new"]
    final = [mapping.get(r.name, r.name) for r in before.rows]
    if len({n.casefold() for n in final}) != len(final):
        raise BridgeError("Renamed structure members would have duplicate names.")
    replacements = [(r.spans["name"][0], r.spans["name"][1], tables.string(mapping[r.name]))
                    for r in before.rows if r.name in mapping and mapping[r.name] != r.name]
    result = replace_spans(raw, replacements)
    after = tables.parse(result, "stru")
    if after.name != before.name or [r.name for r in after.rows] != final:
        raise BridgeError("Renamed structure failed complete definition readback.")
    return result, before, mapping


def replace_spans(raw, replacements):
    end = len(raw)
    for start, stop, value in sorted(replacements, reverse=True):
        if not 0 <= start < stop <= end:
            raise BridgeError("Overlapping or invalid native string spans.")
        raw = raw[:start] + value + raw[stop:]
        end = start
    return raw


def initializer(value, definition, mapping):
    if not value:
        return value  # Observed empty default; no member keys are serialized.
    # Match the complete concrete template, including every original comment.
    # Delimiters inside comments are not parsed, escaped, removed or rewritten.
    # Unknown value-bearing/nested initializers need their own format evidence.
    expected = comment_initializer((r.name, r.comment) for r in definition.rows)
    if value != expected:
        raise BridgeError("Associated structure initializer differs from its exact definition; no unknown metadata was changed.")
    return comment_initializer((mapping.get(r.name, r.name), r.comment)
                               for r in definition.rows)


def fb_initializers(raw, definitions):
    obj = fb.parse(raw)
    replacements, updates = [], []
    for row in obj.variables:
        if row.type_code != 64 or row.type_text not in definitions:
            continue
        definition, mapping = definitions[row.type_text]
        value = initializer(row.initial_raw, definition, mapping)
        if value == row.initial_raw:
            continue
        reader = fb.Reader(raw, row.offset, row.end)
        reader.string(); reader.u32(); reader.string(); reader.string()
        start = reader.pos
        reader.string()
        replacements.append((start, reader.pos, tables.string(value)))
        updates.append(dict(variable=row.name, structure=row.type_text, field="initial_value_raw"))
    result = replace_spans(raw, replacements)
    after = fb.parse(result)
    if (result[after.inner_offset - 4:] != raw[obj.inner_offset - 4:]
            or len(after.variables) != len(obj.variables)):
        raise BridgeError("Associated FB body/envelope changed during member rename.")
    return result, updates
