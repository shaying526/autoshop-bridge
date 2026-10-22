"""Read-only vendor system definitions; no native table writer or layout guesses."""

import re
import xml.etree.ElementTree as ET

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE


def xml_root(raw, expected):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_NATIVE_SIZE:
        raise BridgeError("Unsupported system XML size.")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    else:
        match = re.search(br'encoding\s*=\s*[\"\']([^\"\']+)', raw[:256], re.I)
        declared = match[1].decode("ascii", errors="replace").lower() if match else "utf-8"
        encodings = {"utf-8": "utf-8-sig", "gb2312": "gb18030", "gbk": "gb18030", "gb18030": "gb18030"}
        if declared not in encodings:
            raise BridgeError("Unsupported system XML encoding.")
        encoding = encodings[declared]
    try:
        text = raw.decode(encoding)
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise BridgeError("System XML DTD/entities are unsupported.")
        root = ET.fromstring(text)
    except (UnicodeError, ET.ParseError) as exc:
        raise BridgeError("Invalid system XML.") from exc
    if root.tag != expected:
        raise BridgeError("Unexpected system XML root: " + root.tag)
    stack, count = [(root, 0)], 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > 32 or count > 50000:
            raise BridgeError("System XML node/depth limit exceeded.")
        stack.extend((child, depth + 1) for child in node)
    return root


def field(node, name, required=False):
    matches = node.findall(name)
    if len(matches) > 1:
        raise BridgeError("Duplicate system definition field: " + name)
    value = (matches[0].text or "").strip() if matches else None
    if required and not value:
        raise BridgeError("Missing system definition field: " + name)
    return value


def raw_node(node):
    return dict(tag=node.tag, attributes=dict(node.attrib), text=(node.text or "").strip(),
                children=[raw_node(child) for child in node])


def excluded(node, model):
    value = field(node, "UnEnableModel") or ""
    # Despite its name, the observed IDE treats this as an applicability list.
    return bool(value) and model.casefold() not in {
        s.strip().casefold() for s in value.split("|") if s.strip()
    }


def typed_row(node, name, types):
    if not name or not name.isidentifier():
        raise BridgeError("Invalid system variable/member name.")
    dtype = field(node, "DataType", True)
    if len(dtype) > 256:
        raise BridgeError("System data type name exceeds limit.")
    array = None
    arrays = node.findall("Array")
    if dtype == "ARRAY":
        if len(arrays) != 1:
            raise BridgeError("ARRAY requires one explicit descriptor.")
        element = field(arrays[0], "DataType", True)
        length = field(arrays[0], "Length", True)
        if not length.isdecimal() or len(length) > 8 or not 1 <= int(length) <= 10000000:
            raise BridgeError("Invalid system array length.")
        array = dict(element_type=element, length=int(length),
                     element_bit_length_raw=field(arrays[0], "Bit"),
                     uninterpreted_fields=[raw_node(c) for c in arrays[0]
                                           if c.tag not in ("DataType", "Length", "Bit")])
    elif arrays:
        raise BridgeError("Unexpected system array descriptor.")
    reference = array["element_type"] if array else dtype
    known = types.get(reference)
    return dict(name=name, data_type=dtype, type_reference=reference,
                display_data_type=(reference + "[" + str(array["length"]) + "]") if array else dtype,
                type_code=known["type_code"] if known else None,
                type_resolved=known is not None, array=array,
                comment=field(node, "Comment"), offset_raw=field(node, "Offset"),
                source_attributes=dict(node.attrib),
                model_list_raw=field(node, "UnEnableModel"),
                uninterpreted_fields=[raw_node(c) for c in node if c.tag not in
                                      ("Name", "DataType", "Array", "Comment", "Offset", "UnEnableModel")])


def parse(variables_raw, types_raw, model):
    if not isinstance(model, str) or not model.strip():
        raise BridgeError("System definitions require the project's controller model.")
    model = model.strip()
    variables = xml_root(variables_raw, "SysVarDef")
    definitions = xml_root(types_raw, "DataTypeDef")
    module = field(variables, "ModuleName", True)
    if field(definitions, "ModuleName", True) != module:
        raise BridgeError("System variable/type modules differ.")
    types, originals, type_names = {}, {}, {}
    for section in ("StdDataType", "SysDataType"):
        groups = definitions.findall(section)
        if len(groups) != 1:
            raise BridgeError("System type XML requires one " + section)
        for node in groups[0]:
            if not node.tag.isidentifier():
                raise BridgeError("Invalid system type name.")
            folded = node.tag.casefold()
            if folded in type_names and type_names[folded] != node.tag:
                raise BridgeError("Ambiguous system type spelling: " + node.tag)
            type_names[folded] = node.tag
            signature = raw_node(node)
            if node.tag in types:
                if originals[node.tag] != signature:
                    raise BridgeError("Ambiguous system type definition: " + node.tag)
                types[node.tag]["definition_count"] += 1
                continue
            code = field(node, "TypeCode", True)
            if not code.isdecimal() or len(code) > 10 or int(code) > 0xFFFFFFFF:
                raise BridgeError("Invalid system type code.")
            originals[node.tag] = signature
            types[node.tag] = dict(name=node.tag, type_code=int(code),
                                   bit_length_raw=field(node, "TypeBit"),
                                   source_attributes=dict(node.attrib), members=[], definition_count=1,
                                   uninterpreted_fields=[raw_node(c) for c in node
                                                         if c.tag not in ("TypeCode", "TypeBit", "Struct")])
    for node in definitions.find("SysDataType"):
        info = types[node.tag]
        if info["members"]:
            continue  # Identical repeated declaration was verified above.
        groups = node.findall("Struct")
        if len(groups) != 1:
            raise BridgeError("System structure requires one member group.")
        names = set()
        for member in groups[0]:
            if member.tag != "Member" or len(info["members"]) >= 4096:
                raise BridgeError("Unsupported system structure member layout.")
            name = field(member, "Name", True)
            if name.casefold() in names:
                raise BridgeError("Duplicate system member: " + name)
            names.add(name.casefold())
            info["members"].append(typed_row(member, name, types))
    tables = {}
    for node in variables:
        if node.tag == "ModuleName":
            continue
        if not node.tag.startswith("_SYS_") or node.tag in tables:
            raise BridgeError("Invalid/duplicate system table definition.")
        rows, excluded_count, names = [], 0, set()
        for variable in node:
            if variable.tag == "BaseAddress":
                continue
            if not variable.tag.startswith("_"):
                raise BridgeError("Unknown system table declaration field.")
            if excluded(variable, model):
                excluded_count += 1
                continue
            if variable.tag.casefold() in names:
                raise BridgeError("Ambiguous model-specific system variable: " + variable.tag)
            names.add(variable.tag.casefold())
            rows.append(typed_row(variable, variable.tag, types))
        tables[node.tag] = dict(name=node.tag, base_address_raw=field(node, "BaseAddress", True),
                                variables=rows, excluded_count=excluded_count)
    return dict(module_name=module, model=model, tables=tables, types=types)
