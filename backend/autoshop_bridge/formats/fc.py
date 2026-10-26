"""Observed FC envelope, independent of FB's initializer/retention records."""

import struct
from dataclasses import dataclass
from typing import Tuple

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.fb import Reader, BUILTIN_TYPES, CATEGORIES
from autoshop_bridge.formats import st

PROFILE = "autoshop-fc-embedded-st-v1-experimental"


@dataclass(frozen=True)
class Variable:
    offset: int
    end: int
    type_text: str
    type_code: int
    name: str
    comment: str
    fields: Tuple[int, int, int]

    def as_dict(self, index):
        return dict(display_order=index + 1, name=self.name,
                    category=CATEGORIES.get(self.fields[0]), category_code=self.fields[0],
                    data_type=self.type_text or BUILTIN_TYPES.get(self.type_code),
                    type_text_raw=self.type_text, type_code=self.type_code, comment=self.comment,
                    uninterpreted_fields=list(self.fields[1:]),
                    record_offset=self.offset, record_bytes=self.end - self.offset)


@dataclass(frozen=True)
class FCContainer:
    raw: bytes
    inner_offset: int
    inner: st.Container
    variable_header_offset: int
    program_name: str
    variables: Tuple[Variable, ...]

    @property
    def source(self):
        return self.inner.source

    @property
    def payload_offset(self):
        return self.inner_offset + self.inner.payload_offset

    @property
    def length_offset(self):
        return self.inner_offset + self.inner.length_offset

    @property
    def payload_length(self):
        return self.inner.payload_length

    @property
    def line_count(self):
        return self.source.count(b"\n") + 1

    @property
    def line_table_count(self):
        return self.inner.line_table_count

    @property
    def line_metadata_matches_source(self):
        # New/edited FC saves may retain the previous row count, as with FB.
        # Never infer a different counting convention from one stale save.
        return self.line_table_count == self.line_count

    def variable_document(self):
        return dict(schema=1, read_only=True, program_name=self.program_name,
                    notes=["This FC variable snapshot is read-only; supported variable edits use the editor workflow.",
                           "FC has no decoded initializer or retention columns.",
                           "display_order is not a persistent AutoShop ID; return type is not decoded."],
                    variables=[v.as_dict(i) for i, v in enumerate(self.variables)])

    def rebuild(self, source):
        st.validate_text(source)
        if source != self.source:
            st.validate_program_edit(source)
        if source != self.source and (self.line_count != source.count(b"\n") + 1
                                     or not self.line_metadata_matches_source):
            raise BridgeError("FC file editing requires matching source/line metadata; use editor mode.")
        if source == self.source:
            return self.raw
        result = (self.raw[:self.length_offset] + struct.pack("<I", len(source))
                  + st.encode(source) + self.raw[self.payload_offset + self.payload_length:])
        rebuilt = parse(result)
        if (rebuilt.source != source or rebuilt.variable_document() != self.variable_document()
                or rebuilt.raw[:self.inner_offset] != self.raw[:self.inner_offset]):
            raise BridgeError("Rebuilt FC failed envelope/variable verification.")
        return result


def variable_tables(raw, end):
    for start in range(8, end):
        reader = Reader(raw, start, end)
        try:
            name = reader.string()
            if not name.isidentifier() or len(name) > 255 or reader.u32() != 512:
                continue
            count = reader.u32()
            if count > 4096 or count * 19 > end - reader.pos:
                continue
            rows, names = [], set()
            for _ in range(count):
                offset = reader.pos
                type_text, type_code = reader.string(), reader.u32()
                variable, comment = reader.string(), reader.string()
                fields = tuple(reader.u32() for _ in range(3))
                if (not variable.isidentifier() or variable.casefold() in names
                        or len(type_text) > 512 or any(ord(c) < 32 for c in type_text)):
                    raise BridgeError("Invalid FC variable name/type.")
                names.add(variable.casefold())
                rows.append(Variable(offset, reader.pos, type_text, type_code, variable, comment, fields))
            if reader.pos == end:
                yield start, name, tuple(rows)
        except BridgeError:
            continue


def inner_objects(raw):
    """FC permits zero rows; use only its independent envelope as discriminator."""
    try:
        yield st.parse(raw, allow_line_count_mismatch=True)
        return
    except BridgeError:
        pass
    for offset in range(8, len(raw) - 11):
        length = struct.unpack_from("<I", raw, offset)[0]
        end = offset + 4 + length
        if end != len(raw) - 8 or raw[end:] != b"\0" * 8:
            continue
        source = st.decode(raw[offset + 4:end])
        try:
            st.validate_text(source)
        except BridgeError:
            continue
        yield st.Container(raw, offset, offset + 4, length, source, 0)


def parse(raw):
    if len(raw) > st.MAX_NATIVE_SIZE or not raw.startswith(b"AutoShop") or not raw.endswith(b"\0" * 4):
        raise BridgeError("Unsupported FC envelope or size.")
    found = []
    offset = raw.find(b"AutoShop", 8)
    while offset != -1:
        if raw[offset - 4:offset] == b"\0" * 4:
            for inner in inner_objects(raw[offset:]):
                for start, name, rows in variable_tables(raw, offset - 4):
                    found.append(FCContainer(raw, offset, inner, start, name, rows))
                    if len(found) > 1:
                        raise BridgeError("Ambiguous FC variables/source; refusing to guess.")
        offset = raw.find(b"AutoShop", offset + 1)
    if not found:
        raise BridgeError("Unsupported FC variables/embedded ST layout.")
    return found[0]
