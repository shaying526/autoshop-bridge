"""Rename existing structure members and observed named initializer keys.

Only string spans are replaced. No address, type, order, opaque field or source
reference is changed. A declaration rename is not a business-reference check.
"""
from hashlib import sha256

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats import fb, tables
from autoshop_bridge.formats.array_types import descriptor as array_descriptor
from autoshop_bridge.formats.offline_variables import array_structure_initial
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


def fb_structure_reference(row, definitions):
    """Identify related native defaults without qualifying unrelated types."""
    if row.type_code == 64 and row.type_text in definitions:
        return row.type_text, None
    if row.type_code != 128 or row.type_text.split("[", 1)[0] not in definitions:
        return None
    root = row.type_text.split("[", 1)[0]
    try:
        shape = array_descriptor(row.type_text)
        if shape is None or shape.element_type != root:
            raise FormatRejection("Associated structure ARRAY descriptor is not implemented.",
                                  context=dict(field="data_type", value=row.type_text))
    except FormatRejection as exc:
        exc.context.update(stage="structure_array_rename", variable=row.name,
                           structure=root, profile="fb-structure-array-default-v1")
        raise
    return root, shape.dimensions


def _array_initializer(row, definition, mapping, dimensions):
    if not row.initial_raw:
        return row.initial_raw  # No serialized member keys to synchronize.
    context = dict(stage="structure_array_rename", variable=row.name,
                   structure=definition.name, data_type=row.type_text,
                   dimensions=list(dimensions), profile="fb-structure-array-default-v1")
    try:
        expected = array_structure_initial(definition.raw, definition.name, dimensions)
        renamed, _, _ = structure(definition.raw, [dict(old=k, new=v) for k, v in mapping.items()])
        replacement = array_structure_initial(renamed, definition.name, dimensions)
    except FormatRejection as exc:
        # Keep the exact member/field/value diagnostic from the default codec.
        exc.context.update(context)
        raise
    if row.initial_raw != expected:
        raise FormatRejection(
            "Associated structure ARRAY initializer profile is not implemented: "
            "variable={!r}, structure={!r}; the saved value is not the exact observed default.".format(
                row.name, definition.name),
            code="structure_array_rename_profile_unobserved",
            context=dict(context, field="initial_value_raw", reason="nondefault_initializer",
                         actual_length=len(row.initial_raw), expected_length=len(expected),
                         actual_sha256=sha256(row.initial_raw.encode("utf-8")).hexdigest(),
                         expected_sha256=sha256(expected.encode("utf-8")).hexdigest(),
                         requires="independent_ide_sample"),
        )
    return replacement


def fb_initializers(raw, definitions):
    obj = fb.parse(raw)
    replacements, updates = [], []
    for row in obj.variables:
        reference = fb_structure_reference(row, definitions)
        if reference is None:
            continue
        root, dimensions = reference
        definition, mapping = definitions[root]
        value = (initializer(row.initial_raw, definition, mapping) if dimensions is None
                 else _array_initializer(row, definition, mapping, dimensions))
        if value == row.initial_raw:
            continue
        reader = fb.Reader(raw, row.offset, row.end)
        reader.string(); reader.u32(); reader.string(); reader.string()
        start = reader.pos
        reader.string()
        replacements.append((start, reader.pos, tables.string(value)))
        update = dict(variable=row.name, structure=root, field="initial_value_raw")
        if dimensions is not None:
            update.update(data_type=row.type_text, dimensions=list(dimensions),
                          profile="fb-structure-array-default-v1")
        updates.append(update)
    result = replace_spans(raw, replacements)
    after = fb.parse(result)
    if (result[after.inner_offset - 4:] != raw[obj.inner_offset - 4:]
            or len(after.variables) != len(obj.variables)):
        raise BridgeError("Associated FB body/envelope changed during member rename.")
    return result, updates
