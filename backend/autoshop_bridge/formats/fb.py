"""Observed FB envelope: variable records followed by an embedded ST object.

Offsets are discovered and the envelope is preserved, not regenerated. The
local FB probes cover VAR/IN/OUT/INOUT and BOOL/INT/DINT record codes;
support for editing remains narrower than the read-only record decoder.
"""

import struct
from dataclasses import dataclass
from typing import Tuple

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.st import Container, MAX_NATIVE_SIZE, parse as parse_st

PROFILE = "autoshop-fb-embedded-st-v1-experimental"
BUILTIN_TYPES = {1: "BOOL", 4: "INT", 16: "DINT"}
CATEGORIES = {0: "VAR", 1: "IN", 2: "OUT", 3: "INOUT"}


class Reader:
    def __init__(self, raw: bytes, start: int, end: int):
        self.raw, self.pos, self.end = raw, start, end

    def take(self, count: int) -> bytes:
        if count < 0 or self.pos + count > self.end:
            raise BridgeError("Truncated FB variable record.")
        result = self.raw[self.pos : self.pos + count]
        self.pos += count
        return result

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def string(self) -> str:
        length = self.take(1)[0]
        if length == 255:
            length = struct.unpack("<H", self.take(2))[0]
            if length == 65534:
                raise BridgeError("Unsupported Unicode FB string representation.")
            if length == 65535:
                length = self.u32()
        try:
            return self.take(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BridgeError("Unsupported FB variable string encoding.") from exc


@dataclass(frozen=True)
class Variable:
    offset: int
    end: int
    type_text: str
    type_code: int
    name: str
    comment: str
    initial_raw: str
    fields: Tuple[int, int, int, int]

    def as_dict(self, index: int) -> dict:
        return {
            "display_order": index + 1,
            "name": self.name,
            "category": CATEGORIES.get(self.fields[0]),
            "category_code": self.fields[0],
            "data_type": self.type_text or BUILTIN_TYPES.get(self.type_code),
            "type_text_raw": self.type_text,
            "type_code": self.type_code,
            "comment": self.comment,
            "initial_value_raw": self.initial_raw,
            "uninterpreted_fields": list(self.fields[1:]),
            "record_offset": self.offset,
            "record_bytes": self.end - self.offset,
        }


@dataclass(frozen=True)
class FBContainer:
    raw: bytes
    inner_offset: int
    inner: Container
    variable_header_offset: int
    program_name: str
    variables: Tuple[Variable, ...]

    @property
    def source(self) -> bytes:
        return self.inner.source

    @property
    def payload_offset(self) -> int:
        return self.inner_offset + self.inner.payload_offset

    @property
    def length_offset(self) -> int:
        return self.inner_offset + self.inner.length_offset

    @property
    def payload_length(self) -> int:
        return self.inner.payload_length

    @property
    def line_count(self) -> int:
        return self.source.count(b"\n") + 1

    @property
    def line_table_count(self) -> int:
        return self.inner.line_table_count

    def variable_document(self) -> dict:
        return {
            "schema": 1,
            "read_only": True,
            "program_name": self.program_name,
            "notes": [
                "Only source.st is editable; variable write-back is unsupported.",
                "display_order is not a decoded persistent AutoShop ID.",
                "Retention fields are not decoded; initial values may contain control codes.",
                "Referenced structure/FB type definitions are separate files.",
            ],
            "variables": [item.as_dict(i) for i, item in enumerate(self.variables)],
        }

    def rebuild(self, source: bytes) -> bytes:
        embedded = self.inner.rebuild(source)
        result = self.raw[: self.inner_offset] + embedded + self.raw[-4:]
        if len(result) > MAX_NATIVE_SIZE:
            raise BridgeError("FB result exceeds the supported size limit.")
        rebuilt = parse(result)
        if (
            rebuilt.source != source
            or rebuilt.variable_document() != self.variable_document()
            or rebuilt.raw[: self.inner_offset] != self.raw[: self.inner_offset]
        ):
            raise BridgeError("Rebuilt FB failed envelope/variable verification.")
        return result


def variable_tables(raw: bytes, end: int):
    """Locate a complete name/count/record sequence ending at the inner object."""
    for start in range(8, end):
        reader = Reader(raw, start, end)
        try:
            name = reader.string()
            if not name.isidentifier() or len(name) > 255 or reader.u32() != 256:
                continue
            count = reader.u32()
            if count > 4096 or count * 23 > end - reader.pos:
                continue
            rows = []
            names = set()
            for _ in range(count):
                offset = reader.pos
                type_text, type_code = reader.string(), reader.u32()
                var_name, comment, initial = (
                    reader.string(),
                    reader.string(),
                    reader.string(),
                )
                fields = tuple(reader.u32() for _ in range(4))
                if (
                    not var_name.isidentifier()
                    or var_name in names
                    or len(type_text) > 512
                    or any(ord(char) < 32 for char in type_text)
                ):
                    raise BridgeError("Invalid or duplicate FB variable name/type.")
                names.add(var_name)
                rows.append(
                    Variable(
                        offset,
                        reader.pos,
                        type_text,
                        type_code,
                        var_name,
                        comment,
                        initial,
                        fields,
                    )
                )
            if reader.pos == end:
                yield start, name, tuple(rows)
        except BridgeError:
            continue


def parse(raw: bytes) -> FBContainer:
    if (
        len(raw) > MAX_NATIVE_SIZE
        or not raw.startswith(b"AutoShop")
        or not raw.endswith(b"\0\0\0\0")
    ):
        raise BridgeError("Unsupported FB envelope or size.")
    found = []
    offset = raw.find(b"AutoShop", 8)
    while offset != -1:
        if raw[offset - 4 : offset] == b"\0\0\0\0":
            try:
                # Observed AutoShop save after FB editor insertion preserves
                # the old row table. Read both counts; never regenerate it.
                inner = parse_st(raw[offset:-4], allow_line_count_mismatch=True)
            except BridgeError:
                inner = None
            if inner is not None:
                for start, name, rows in variable_tables(raw, offset - 4):
                    found.append(FBContainer(raw, offset, inner, start, name, rows))
                    if len(found) > 1:
                        raise BridgeError(
                            "Ambiguous FB envelope/variable tables; refusing to guess."
                        )
        offset = raw.find(b"AutoShop", offset + 1)
    if not found:
        raise BridgeError(
            "Unsupported FB layout: no unique variables/embedded ST match."
        )
    return found[0]
