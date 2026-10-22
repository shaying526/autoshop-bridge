"""Strict read-only recognition of the observed structure member sequence."""

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.fb import Reader
from autoshop_bridge.formats.tables import TYPES as BUILTIN_TYPES
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE


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
