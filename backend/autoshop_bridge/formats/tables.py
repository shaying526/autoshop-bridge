"""Strict observed STRU/GVT records; mutate selected strings, preserve opaque bytes."""

import re
import struct
from dataclasses import dataclass

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.fb import Reader
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE

TYPES = {1: "BOOL", 4: "INT", 16: "DINT"}  # 16 confirmed by STRU/GVT UI readback.
SCALAR_CODES = {1, 4, 16, 32}
ADD_TYPES = {"BOOL": 1, "INT": 4, "DINT": 16}
UNALLOCATED_ADDRESS = 0xFFFFFFFF  # AutoShop's saved new-scalar address sentinel.


def comment_display(text):
    """Translate the two observed native comment separators for presentation."""
    return text.replace("\x06", ":").replace("\x08", "=")


def string(value):
    data = value.encode("utf-8")
    if len(data) < 255:
        return bytes([len(data)]) + data
    if len(data) < 65534:
        return b"\xff" + struct.pack("<H", len(data)) + data
    raise BridgeError("Table string exceeds supported length.")


def read_string(reader, spans, key):
    start = reader.pos
    value = reader.string()
    spans[key] = (start, reader.pos)
    return value


def unicode_string(reader):
    if reader.take(3) != b"\xff\xfe\xff":
        raise BridgeError("Unsupported GVT device-address string encoding.")
    length = reader.take(1)[0]
    if length == 255:
        length = struct.unpack("<H", reader.take(2))[0]
        if length == 65535:
            length = reader.u32()
    try:
        return reader.take(length * 2).decode("utf-16-le")
    except UnicodeError as exc:
        raise BridgeError("Invalid GVT device-address string.") from exc


def identifier(value):
    return (
        isinstance(value, str)
        and value.isidentifier()
        and value[0].isalpha()
        and len(value.encode("utf-8")) <= 63
        and value.upper()
        not in {
            "BOOL",
            "INT",
            "DINT",
            "REAL",
            "STRING",
            "TRUE",
            "FALSE",
            "ON",
            "OFF",
            "ARRAY",
            "NULL",
            "IF",
            "THEN",
            "ELSE",
            "ELSIF",
            "END_IF",
            "CASE",
            "OF",
            "END_CASE",
            "FOR",
            "TO",
            "BY",
            "DO",
            "END_FOR",
            "WHILE",
            "END_WHILE",
            "REPEAT",
            "UNTIL",
            "END_REPEAT",
            "EXIT",
            "RETURN",
            "VAR",
            "VAR_INPUT",
            "VAR_OUTPUT",
            "VAR_IN_OUT",
            "END_VAR",
            "STRUCT",
            "END_STRUCT",
            "TYPE",
            "END_TYPE",
            "PROGRAM",
            "FUNCTION",
            "FUNCTION_BLOCK",
            "AND",
            "OR",
            "NOT",
            "XOR",
            "MOD",
        }
    )


def addition(op, kind):
    fields = {"op", "name", "data_type", "comment"}
    if kind == "gvt":
        fields.add("initial_value")
    if (
        set(op) != fields
        or not isinstance(op.get("data_type"), str)
        or op["data_type"] not in ADD_TYPES
        or not identifier(op.get("name"))
    ):
        raise BridgeError(
            "Add requires an exact valid name, BOOL/INT/DINT data_type, comment"
            + (" and initial_value." if kind == "gvt" else ".")
        )
    code = ADD_TYPES[op["data_type"]]
    probe = Row(0, 0, op["name"], code, "", "", None, {}, {})
    validate_value(probe, "comment", op["comment"])
    initial = op.get("initial_value")
    if kind == "gvt":
        validate_value(probe, "initial_value", initial)
    return code, initial


def validate_value(row, field, value):
    if (
        not isinstance(value, str)
        or len(value.encode("utf-8")) > 4096
        or any(ord(c) < 32 for c in value)
    ):
        raise BridgeError(
            "Table value must be a bounded string without control characters."
        )
    if field == "comment":
        return
    if field == "initial_value" and row.type_code == 1 and value in ("ON", "OFF"):
        return
    if (
        field == "initial_value"
        and row.type_code in (4, 16)
        and re.fullmatch(r"-?(0|[1-9][0-9]*)", value)
    ):
        bits = 16 if row.type_code == 4 else 32
        if (
            -(2 ** (bits - 1)) <= int(value) < 2 ** (bits - 1)
            and str(int(value)) == value
        ):
            return
    raise BridgeError(
        "Only comments and BOOL/INT/DINT scalar initial values can be changed."
    )


@dataclass(frozen=True)
class Row:
    start: int
    end: int
    name: str
    type_code: int
    type_text: str
    comment: str
    initial_raw: object
    spans: dict
    metadata: dict

    def document(self):
        return dict(
            name=self.name,
            type_code=self.type_code,
            type_text_raw=self.type_text,
            data_type=(self.type_text or TYPES.get(self.type_code))
            if self.type_code != 128
            else None,
            comment=self.comment,
            initial_value_raw=self.initial_raw,
            uninterpreted_metadata=self.metadata,
        )


@dataclass(frozen=True)
class Table:
    raw: bytes
    kind: str
    name: str
    count_offset: int
    rows: tuple

    def document(self):
        return dict(
            schema=1,
            read_only=True,
            kind=self.kind,
            name=self.name,
            row_count=len(self.rows),
            rows=[r.document() for r in self.rows],
        )

    def rebuild(self, operations):
        if not isinstance(operations, list) or len(operations) > 32:
            raise BridgeError(
                "Expected a list of at most 32 explicit table operations."
            )
        result = self.raw
        if self.kind == "gvt" and not self.rows and operations:
            raise BridgeError("Empty GVT recognition is read-only; file-mode initialization is not validated.")
        for op in operations:
            current = parse(result, self.kind)
            if not isinstance(op, dict):
                raise BridgeError("Table operation must be an object.")
            if op.get("op") == "set":
                if set(op) != {"op", "name", "field", "expected", "value"}:
                    raise BridgeError("Set requires exact name/field/expected/value.")
                matches = [r for r in current.rows if r.name == op["name"]]
                if len(matches) != 1:
                    raise BridgeError("Expected one exact table row name.")
                row = matches[0]
                field = op["field"]
                if (
                    not isinstance(field, str)
                    or field not in ("comment", "initial_value")
                    or field not in row.spans
                ):
                    raise BridgeError("Unsupported field for this table.")
                before = row.comment if field == "comment" else row.initial_raw
                if not isinstance(op["expected"], str) or before != op["expected"]:
                    raise BridgeError(
                        "Table field baseline differs: {}.".format(row.name)
                    )
                validate_value(row, field, op["value"])
                if before == op["value"]:
                    continue
                start, end = row.spans[field]
                result = result[:start] + string(op["value"]) + result[end:]
            elif op.get("op") == "add":
                code, initial = addition(op, current.kind)
                if any(
                    r.name.casefold() == op["name"].casefold() for r in current.rows
                ):
                    raise BridgeError("Duplicate table member/variable.")
                if len(current.rows) >= 4096:
                    raise BridgeError("Table row limit exceeded.")
                if current.kind == "stru":
                    encoded = (
                        string("")
                        + struct.pack("<I", code)
                        + string(op["name"])
                        + string(op["comment"])
                    )
                else:
                    # Default flags/tail observed in new BOOL/INT and existing
                    # ordinary DINT records. DINT additions await live acceptance.
                    # the IDE/compiler allocates addresses, never this encoder.
                    encoded = (
                        struct.pack("<II", code, code)
                        + string(op["name"])
                        + string(initial)
                        + struct.pack("<II", 257, UNALLOCATED_ADDRESS)
                        + string(op["comment"])
                        + b"\xff\xfe\xff\0"
                        + struct.pack("<II", 0, 0)
                    )
                pos = current.count_offset
                result = (
                    result[:pos]
                    + struct.pack("<I", len(current.rows) + 1)
                    + result[pos + 4 :]
                    + encoded
                )
            else:
                raise BridgeError(
                    "Unsupported table operation; type/address/retention/rename/delete are pending."
                )
            if len(result) > MAX_NATIVE_SIZE:
                raise BridgeError("Table result exceeds size limit.")
            parse(result, self.kind)
        return result


def struct_rows(raw, reader, count):
    rows, names = [], set()
    for _ in range(count):
        start, spans = reader.pos, {}
        text, code = reader.string(), reader.u32()
        name = read_string(reader, spans, "name")
        comment = read_string(reader, spans, "comment")
        if (
            not name.isidentifier()
            or name.casefold() in names
            or len(text) > 512
            or any(ord(c) < 32 for c in text)
        ):
            raise BridgeError("Invalid structure member.")
        names.add(name.casefold())
        rows.append(Row(start, reader.pos, name, code, text, comment, None, spans, {}))
    return tuple(rows)


def gvt_rows(raw, reader, count):
    rows, names = [], set()
    for _ in range(count):
        start, spans = reader.pos, {}
        code, related = reader.u32(), reader.u32()
        if code not in SCALAR_CODES | {64, 128} or related != code:
            raise BridgeError("Unsupported GVT type descriptor.")
        name = read_string(reader, spans, "name")
        initial = read_string(reader, spans, "initial_value")
        if not name.isidentifier() or name.casefold() in names:
            raise BridgeError("Invalid/duplicate GVT variable name.")
        names.add(name.casefold())
        flags, address = reader.u32(), reader.u32()
        comment = read_string(reader, spans, "comment")
        device = unicode_string(reader)
        fields = [reader.u32(), reader.u32()]
        metadata = dict(
            related_type_code=related,
            flags_raw=flags,
            address_raw=address,
            device_address_text=device,
            trailing_fields_raw=fields,
        )
        text = ""
        if code == 64:
            text = reader.string()
            if not text.isidentifier():
                raise BridgeError("Invalid GVT structure reference.")
        elif code == 128:
            marker = reader.take(1)
            prefix = [reader.u32() for _ in range(3)]
            if (
                marker != b"\0"
                or prefix[0] != 128
                or prefix[1] not in SCALAR_CODES | {64}
                or not 1 <= prefix[2] <= 1000000
            ):
                raise BridgeError("Unsupported GVT array descriptor.")
            if prefix[1] == 64:
                text = reader.string()
                if not text.isidentifier():
                    raise BridgeError("Invalid GVT array structure reference.")
            metadata["array_descriptor_raw"] = prefix
            metadata["array_trailer_raw"] = [reader.u32() for _ in range(3)]
        rows.append(
            Row(start, reader.pos, name, code, text, comment, initial, spans, metadata)
        )
    return tuple(rows)


def parse(raw, kind):
    if (
        kind not in ("stru", "gvt")
        or len(raw) > MAX_NATIVE_SIZE
        or not raw.startswith(b"AutoShop")
    ):
        raise BridgeError("Unsupported native table kind/header/size.")
    found = []
    if kind == "gvt":
        from autoshop_bridge.formats.empty_table import count_offset
        offset = count_offset(raw)
        if offset is not None:
            found.append(Table(raw, kind, "", offset, ()))
    for start in range(8, min(len(raw), 4096)):
        reader = Reader(raw, start, len(raw))
        try:
            if kind == "stru":
                name = reader.string()
                if not name.isidentifier() or reader.u32() != 64:
                    continue
                count_offset = reader.pos
                count = reader.u32()
                if count > 4096 or count * 7 > len(raw) - reader.pos:
                    continue
                rows = struct_rows(raw, reader, count)
            else:
                name, count_offset = "", reader.pos
                count = reader.u32()
                if not 1 <= count <= 4096 or count * 29 > len(raw) - reader.pos:
                    continue
                rows = gvt_rows(raw, reader, count)
            if reader.pos == len(raw):
                found.append(Table(raw, kind, name, count_offset, rows))
        except BridgeError:
            continue
    if len(found) != 1:
        raise BridgeError("Unsupported/ambiguous {} table layout.".format(kind.upper()))
    return found[0]
