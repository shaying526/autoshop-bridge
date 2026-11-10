"""Strict observed STRU/GVT records; mutate selected strings, preserve opaque bytes."""

import re
import struct
from dataclasses import dataclass

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats.fb import Reader
from autoshop_bridge.formats.array_types import descriptor as array_descriptor, from_gvt_row, structure_element
from autoshop_bridge.formats.scalar_types import descriptor, BYTE_IP_CODES
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE

TYPES = {1: "BOOL", 4: "INT", 16: "DINT", 32: "REAL", 8192: "BYTE", 4096: "IP"}
# Fixed-width element layouts already observed in GVT ARRAY descriptors.
# Standalone STRING has its own trailing descriptor, not this ARRAY profile.
SCALAR_CODES = {1, 4, 16, 32, 4096, 8192}
STANDALONE_SCALAR_CODES = SCALAR_CODES | BYTE_IP_CODES
ADD_TYPES = {"BOOL": 1, "INT": 4, "DINT": 16, "REAL": 32}  # Legacy fixed-width enumeration; use descriptor for additions.
UNALLOCATED_ADDRESS = 0xFFFFFFFF  # AutoShop's saved new-scalar address sentinel.


def comment_display(text):
    """Translate the two observed native comment separators for presentation."""
    return text.replace("\x06", ":").replace("\x08", "=")


def structure_comment_display(text):
    """Display only the independently observed STRU comment separators.

    Native documents retain their raw comment strings. GVT/FBI keep the
    separate legacy 6/8 presentation profile; do not infer this from text.
    """
    return comment_display(text).replace("\x03", "(").replace("\x04", ")").replace("\x05", ",")


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


@dataclass(frozen=True)
class RegisteredStructureDescriptor:
    """Exact root declaration identity; no member defaults or business graph."""
    type_text: str
    code: int = 64

    @property
    def canonical(self):
        return self.type_text


def registered_structure_definition(name, definitions):
    """Qualify one supplied nonempty STRU root without interpreting its members."""
    if (not isinstance(name, str) or not name.isidentifier()
            or not isinstance(definitions, dict) or not isinstance(definitions.get(name), bytes)):
        raise BridgeError('Named structure requires an exact native root name/bytes mapping.')
    definition = parse(definitions[name], 'stru')
    if definition.name != name or not definition.rows:
        raise BridgeError('Named structure requires the exact nonempty native STRU identity.')
    return definition


def addition_type(op, kind, structure_definitions=None):
    """Scalar/ARRAY identity, or a registered STRU member; no named defaults."""
    scalar = descriptor(op.get("data_type"))
    array = array_descriptor(op.get("data_type")) if scalar is None else None
    if array is not None:
        element = descriptor(array.element_type)
        allowed_elements = SCALAR_CODES | {2048}
        if element is None and kind in ("stru", "gvt"):
            structure_element(array.element_type, {} if structure_definitions is None else structure_definitions)
        elif kind not in ("stru", "gvt") or element is None or element.code not in allowed_elements:
            raise FormatRejection(
                "Table ARRAY addition profile is not implemented for this host/element.",
                code="offline_array_profile_unobserved",
                context=dict(stage="table_array_addition", kind=kind, data_type=op.get("data_type"),
                             field="element_type", value=array.element_type,
                             reason="host_or_element_profile_unobserved", requires="independent_ide_sample"),
            )
        total = array.dimensions[0] if len(array.dimensions) == 1 else array.dimensions[0] * array.dimensions[1]
        if kind == "gvt" and (total > 0xFFFFFFFF or any(n > 0xFFFFFFFF for n in array.dimensions)):
            raise FormatRejection(
                "GVT ARRAY count/dimensions exceed the native unsigned DWORD fields.",
                code="array_type_invalid",
                context=dict(stage="gvt_array_descriptor", field="dimensions", value=list(array.dimensions),
                             data_type=op["data_type"], reason="native_u32_field_overflow"),
            )
    if scalar is None and array is None and kind == 'stru':
        registered_structure_definition(op.get('data_type'), structure_definitions)
        return RegisteredStructureDescriptor(op['data_type'])
    return scalar or array


def addition(op, kind, structure_definitions=None):
    fields = {"op", "name", "data_type", "comment"}
    if kind == "gvt":
        fields.add("initial_value")
    scalar = addition_type(op, kind, structure_definitions)
    if (
        set(op) != fields
        or scalar is None
        or not identifier(op.get("name"))
    ):
        raise BridgeError(
            "Add requires an exact valid name, supported declaration data_type, comment"
            + (" and initial_value." if kind == "gvt" else ".")
        )
    code = scalar.code
    probe = Row(0, 0, op["name"], code, "", "", None, {}, {})
    validate_value(probe, "comment", op["comment"])
    initial = op.get("initial_value")
    if kind == "gvt":
        if code == 128:
            if initial is not None:
                raise FormatRejection(
                    "GVT ARRAY additions require initial_value=null for the observed empty default.",
                    code="offline_array_initial_value_unobserved",
                    context=dict(stage="gvt_array_initializer", field="initial_value", value=initial,
                                 data_type=op["data_type"], reason="explicit_array_initializer_unobserved"),
                )
            initial = ""
        else:
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
    if field == "initial_value" and row.type_code in BYTE_IP_CODES:
        # These standalone FB/GVT fields were observed as native strings. Keep
        # the caller's spelling; the compiler owns literal/business semantics.
        return
    if field == "initial_value" and row.type_code == 32:
        # Native REAL initial values are stored as text. Preserve the caller's
        # exact literal; AutoShop compilation, not Python float conversion,
        # determines its PLC syntax and business meaning.
        return
    if field == "initial_value" and row.type_code == 2048:
        # STRING initializers occupy the same bounded native text field. Keep
        # exact caller text; do not derive byte capacity from the literal.
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
        "Only comments and supported scalar initial values can be changed."
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
        data_type = self.type_text or TYPES.get(self.type_code)
        array_diagnostic = None
        if self.type_code == 128:
            try:
                # GVT carries the element/count/dimensions in a separate
                # native descriptor; STRU stores the entire type CString.
                # Reading either identity requires no project definitions.
                array = (from_gvt_row(self) if "related_type_code" in self.metadata
                         else array_descriptor(self.type_text))
            except FormatRejection as exc:
                # This is a read-only projection of an already framed native
                # row, not addition eligibility. Old invalid/unobserved type
                # semantics must not block reading or editing another row.
                array = None
                array_diagnostic = dict(code=exc.code, context=exc.context)
            data_type = array.canonical if array is not None else None
        result = dict(
            name=self.name,
            type_code=self.type_code,
            type_text_raw=self.type_text,
            data_type=data_type,
            comment=self.comment,
            initial_value_raw=self.initial_raw,
            uninterpreted_metadata=self.metadata,
        )
        if array_diagnostic is not None:
            result["array_type_diagnostic"] = array_diagnostic
        return result


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

    def rebuild(self, operations, structure_definitions=None):
        if not isinstance(operations, list) or len(operations) > 32:
            raise BridgeError(
                "Expected a list of at most 32 explicit table operations."
            )
        result = self.raw
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
                    or field not in ("name", "comment", "initial_value")
                    or field not in row.spans
                    or (field == "name" and current.kind != "stru")
                ):
                    raise BridgeError("Unsupported field for this table.")
                before = row.name if field == "name" else row.comment if field == "comment" else row.initial_raw
                if not isinstance(op["expected"], str) or before != op["expected"]:
                    raise BridgeError(
                        "Table field baseline differs: {}.".format(row.name)
                    )
                if field == "name":
                    if not identifier(op["value"]) or any(
                            r is not row and r.name.casefold() == op["value"].casefold() for r in current.rows):
                        raise BridgeError("Invalid or duplicate structure member name.")
                else:
                    validate_value(row, field, op["value"])
                if before == op["value"]:
                    continue
                start, end = row.spans[field]
                result = result[:start] + string(op["value"]) + result[end:]
            elif op.get("op") == "add":
                code, initial = addition(op, current.kind, structure_definitions)
                if any(
                    r.name.casefold() == op["name"].casefold() for r in current.rows
                ):
                    raise BridgeError("Duplicate table member/variable.")
                if len(current.rows) >= 4096:
                    raise BridgeError("Table row limit exceeded.")
                if current.kind == "stru":
                    encoded = (
                        string(addition_type(op, current.kind, structure_definitions).type_text)
                        + struct.pack("<I", code)
                        + string(op["name"])
                        + string(op["comment"])
                    )
                else:
                    # Empty/nonempty BOOL/INT/DINT saves share this observed
                    # default record. The IDE/compiler allocates addresses,
                    # never this encoder; the opaque table prefix stays intact.
                    encoded = (
                        struct.pack("<II", code, code)
                        + string(op["name"])
                        + string(initial)
                        + struct.pack("<II", 257, UNALLOCATED_ADDRESS)
                        + string(op["comment"])
                        + b"\xff\xfe\xff\0"
                        + struct.pack("<II", 0, 0)
                    )
                    if code == 2048:
                        # Independent normal GVT STRING save: the common row
                        # is followed by its capacity-bearing type text and a
                        # repeated STRING descriptor code. Not an ARRAY tail.
                        encoded += string(descriptor(op["data_type"]).type_text) + struct.pack("<I", 2048)
                    elif code == 128:
                        array = array_descriptor(op["data_type"])
                        element = descriptor(array.element_type)
                        element_code = element.code if element is not None else 64
                        total = array.dimensions[0] if len(array.dimensions) == 1 else array.dimensions[0] * array.dimensions[1]
                        trailer = (0, 1, 1) if len(array.dimensions) == 1 else (1, *array.dimensions)
                        encoded += b"\0" + struct.pack("<III", 128, element_code, total)
                        if element_code == 2048:
                            # ARRAY element capacity is one CString between
                            # prefix and trailer, with no standalone STRING's
                            # repeated 2048 DWORD.
                            encoded += string(descriptor(array.element_type).type_text)
                        elif element_code == 64:
                            # Named structure ARRAYs use the exact root name;
                            # their new GVT native initializer remains empty,
                            # independently from FB's value/comment template.
                            encoded += string(array.element_type)
                        encoded += struct.pack("<III", *trailer)
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
            verified = parse(result, self.kind)
            if op.get("op") == "add" and code == 128:
                if (verified.count_offset != current.count_offset
                        or result[:verified.count_offset] != current.raw[:current.count_offset]
                        or len(verified.rows) != len(current.rows) + 1
                        or any(current.raw[a.start:a.end] != result[b.start:b.end]
                               for a, b in zip(current.rows, verified.rows))):
                    raise BridgeError("ARRAY addition changed old records or the opaque table prefix.")
                if self.kind == "gvt" and from_gvt_row(verified.rows[-1]) != array_descriptor(op["data_type"]):
                    raise BridgeError("GVT ARRAY candidate differs from requested element/dimensions.")
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


def _read_array_descriptor(reader):
    """Read the observed ARRAY field frame, retaining uninterpreted trailer values."""
    marker = reader.take(1)
    prefix = [reader.u32() for _ in range(3)]
    if (marker != b"\0" or prefix[0] != 128
            or prefix[1] not in SCALAR_CODES | {64, 2048}
            or not 1 <= prefix[2] <= 0xFFFFFFFF):
        raise BridgeError("Unsupported GVT array descriptor.")
    text = ""
    if prefix[1] == 64:
        text = reader.string()
        if not text.isidentifier():
            raise BridgeError("Invalid GVT array structure reference.")
    elif prefix[1] == 2048:
        text = reader.string()
        element = descriptor(text)
        if element is None or element.code != 2048 or element.canonical != text:
            raise BridgeError("Unsupported GVT ARRAY STRING element descriptor.")
    return text, prefix, [reader.u32() for _ in range(3)]


def gvt_rows(raw, reader, count):
    rows, names = [], set()
    for _ in range(count):
        start, spans = reader.pos, {}
        code, related = reader.u32(), reader.u32()
        if code not in STANDALONE_SCALAR_CODES | {64, 128, 2048} or related != code:
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
        elif code == 2048:
            text = reader.string()
            scalar = descriptor(text)
            repeated_code = reader.u32()
            if scalar is None or scalar.code != 2048 or scalar.canonical != text or repeated_code != 2048:
                raise BridgeError("Unsupported GVT STRING descriptor.")
            metadata["string_descriptor_code_raw"] = repeated_code
        elif code == 128:
            text, prefix, trailer = _read_array_descriptor(reader)
            metadata["array_descriptor_raw"] = prefix
            metadata["array_trailer_raw"] = trailer
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
    archive_count_offsets = []
    if kind == "gvt":
        from autoshop_bridge.formats.empty_table import count_offset, DECLARATION_TAIL
        offset = count_offset(raw)
        if offset is not None:
            found.append(Table(raw, kind, "", offset, ()))
        # Normal empty and nonempty samples have this exact CArchive class
        # definition immediately before the declaration count. Recognizing it
        # adds a necessary framing check without rewriting opaque header bytes.
        class_prefix = DECLARATION_TAIL[:-4]
        position = raw.find(class_prefix, 8, min(len(raw), 4096))
        while position >= 0:
            possible_count = position + len(class_prefix)
            if possible_count == offset:
                archive_count_offsets.append(possible_count)
            else:
                try:
                    signature = Reader(raw, possible_count, len(raw))
                    count = signature.u32()
                    if 0 <= count <= 4096:
                        # Once the observed class definition has a plausible
                        # declaration count, invalid code/related/name bytes
                        # are a damaged real table, never an opaque extension
                        # that licenses a suffix table instead.
                        archive_count_offsets.append(possible_count)
                    else:
                        # A damaged oversized count is not sufficient to
                        # abandon a still-recognizable first record either.
                        code, related = signature.u32(), signature.u32()
                        # A count damaged beyond bounds plus one damaged
                        # field still leaves a recognizable record start.
                        # Refuse this incomplete observed table rather than
                        # treating its serialized body as opaque extension.
                        known_codes = STANDALONE_SCALAR_CODES | {64, 128, 2048}
                        if (code in known_codes or related in known_codes
                                or signature.string().isidentifier()):
                            archive_count_offsets.append(possible_count)
                except BridgeError:
                    pass  # Opaque header extensions retain dynamic discovery.
            position = raw.find(class_prefix, position + 1, min(len(raw), 4096))
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
    if kind == "gvt" and archive_count_offsets:
        if len(archive_count_offsets) != 1 or not any(
                candidate.count_offset == archive_count_offsets[0] for candidate in found):
            raise BridgeError("Observed GVT class header has no unique complete declaration table.")
    if kind == "gvt" and len(found) > 1:
        # A known ARRAY's last trailer DWORD can accidentally look like a
        # second table count followed by the exact suffix of the real table.
        # Remove only candidates proved inside that fully decoded parent row;
        # neither a first/minimum-offset preference nor opaque guessing.
        embedded = set()
        for index, candidate in enumerate(found):
            for parent in found:
                if parent is candidate:
                    continue
                for row_index, row in enumerate(parent.rows):
                    if row.type_code != 128 or candidate.count_offset != row.end - 4:
                        continue
                    suffix = parent.rows[row_index + 1:]
                    if not suffix or candidate.rows != suffix:
                        continue
                    # gvt_rows has authenticated this complete record frame.
                    # Its old raw trailer need not have decoded dimensions;
                    # no values are changed or generated from that old row.
                    embedded.add(index)
        found = [candidate for index, candidate in enumerate(found) if index not in embedded]
    if kind == "gvt" and len(found) == 1 and found[0].count_offset not in archive_count_offsets:
        # A damaged real table can leave only an apparently valid suffix. Its
        # alleged count must not be a field of an independently recognized
        # ARRAY descriptor, even when the enclosing record no longer parses.
        # Reuse the exact field reader; never guess an unknown record layout.
        possible_count = found[0].count_offset
        marker = b"\0" + struct.pack("<I", 128)
        position = raw.find(marker, 8, possible_count)
        while position >= 0:
            probe = Reader(raw, position, len(raw))
            try:
                _read_array_descriptor(probe)
            except BridgeError:
                pass
            else:
                if position < possible_count and possible_count + 4 <= probe.pos:
                    raise BridgeError("GVT declaration count overlaps a serialized ARRAY field; complete parent table is required.")
            position = raw.find(marker, position + 1, possible_count)
    if len(found) != 1:
        raise BridgeError("Unsupported/ambiguous {} table layout.".format(kind.upper()))
    return found[0]
