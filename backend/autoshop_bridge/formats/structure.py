"""Observed structure member sequences and comment-default serialization."""

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats.fb import Reader
from autoshop_bridge.formats.scalar_types import descriptor
from autoshop_bridge.formats.tables import TYPES as BUILTIN_TYPES
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE


def flat_scalar_definition(raw, name):
    """Qualify the observed flat scalar members, not their default grammar.

    The declaration record pairs code with native type text. STRING capacity
    must be explicit and canonical; accepting code 2048 alone would also admit
    unknown descriptors. This never qualifies ARRAY/nested/default layouts.
    """
    from autoshop_bridge.formats import tables

    definition = tables.parse(raw, "stru")
    if definition.name != name or not definition.rows:
        raise BridgeError("Expected the exact nonempty structure definition.")
    for index, row in enumerate(definition.rows):
        dtype = row.type_text or BUILTIN_TYPES.get(row.type_code)
        scalar = descriptor(dtype)
        text_matches = (scalar is not None and (
            row.type_text == scalar.type_text if scalar.string_length is not None
            else row.type_text in ("", scalar.canonical)))
        if scalar is None or scalar.code != row.type_code or not text_matches:
            value = dict(type_code=row.type_code, type_text_raw=row.type_text)
            raise FormatRejection(
                "Structure member scalar descriptor is not implemented: "
                "structure={!r}, member={} {!r}, type_code={}, type_text={!r}.".format(
                    name, index + 1, row.name, row.type_code, row.type_text),
                code="offline_structure_member_unobserved",
                context=dict(stage="flat_structure_member", structure=name,
                             member=row.name, member_index=index, field="data_type",
                             value=value, index_base=0, reason="unobserved_scalar_descriptor"),
            )
    return definition


def comment_initializer(members):
    """Serialize ordered (name, comment) pairs using the IDE default grammar.

    V4.11.0.5 emits only commented members, but appends a separator according
    to the member's original position. A final uncommented member therefore
    leaves a trailing comma and space. An entirely uncommented type is empty.
    Callers qualify types/text; this helper neither parses nor escapes comments.
    """
    members = tuple(members)
    parts = [name + ":=\x07" + comment + (", " if index < len(members) - 1 else "")
             for index, (name, comment) in enumerate(members) if comment]
    return "(" + "".join(parts) + ")" if parts else ""


def parse(raw):
    if len(raw) > MAX_NATIVE_SIZE or not raw.startswith(b"AutoShop"):
        raise BridgeError("Unsupported structure header/size.")
    found = []
    for start in range(8, min(len(raw), 4096)):
        reader = Reader(raw, start, len(raw))
        try:
            name = reader.string()
            if not name.isidentifier() or reader.u32() != 64:
                continue
            count = reader.u32()
            if count > 4096 or count * 7 > len(raw) - reader.pos:
                continue
            members, names = [], set()
            for index in range(count):
                type_text, code = reader.string(), reader.u32()
                member, comment = reader.string(), reader.string()
                if (
                    not member.isidentifier()
                    or member.casefold() in names
                    or len(type_text) > 512
                    or any(ord(c) < 32 for c in type_text)
                ):
                    raise BridgeError("Invalid structure member.")
                names.add(member.casefold())
                members.append(
                    dict(
                        display_order=index + 1,
                        name=member,
                        comment=comment,
                        data_type=type_text or BUILTIN_TYPES.get(code),
                        type_text_raw=type_text,
                        type_code=code,
                    )
                )
            if reader.pos == len(raw):
                found.append(
                    dict(
                        schema=1,
                        read_only=True,
                        name=name,
                        kind_code=64,
                        members=members,
                    )
                )
        except BridgeError:
            continue
    if len(found) != 1:
        raise BridgeError("Unsupported/ambiguous structure member layout.")
    return found[0]
