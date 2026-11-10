"""Pure observed ARRAY type text, separate from native container profiles.

Recognition supplies no initializer, address or GVT descriptor bytes. Named
elements keep their exact spelling and still require the caller's registered
structure context. It does not qualify FB elements or a PLC's array limits.
"""
from dataclasses import dataclass
import re
from typing import Tuple

from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.formats.scalar_types import MAX_NATIVE_TYPE_TEXT, descriptor as scalar_descriptor


@dataclass(frozen=True)
class ArrayDescriptor:
    element_type: str
    dimensions: Tuple[int, ...]
    canonical: str
    type_text: str
    code: int = 128


def _reject(dtype, field, value, reason, *, unobserved=False):
    context = dict(stage="array_type_descriptor", data_type=dtype,
                   field=field, value=value, reason=reason)
    if unobserved:
        context["requires"] = "independent_ide_sample"
    raise FormatRejection(
        "ARRAY type {}: field={!r}, value={!r}, reason={}.".format(
            "profile is not implemented" if unobserved else "is invalid",
            field, value, reason),
        code="array_type_profile_unobserved" if unobserved else "array_type_invalid",
        context=context,
    )


def descriptor(dtype):
    """Recognize saved ``Element[n]`` or ``Element[n,m]`` text, or return None.

    BOOL/INT/DINT/REAL/BYTE/IP use the scalar spelling; STRING retains explicit native
    capacity. An identifier element remains an unresolved named structure
    identity, not a fabricated definition. The
    positive count has no guessed PLC/business ceiling. Unknown ARRAY shapes
    fail explicitly, instead of silently falling into named-type resolution.
    """
    if not isinstance(dtype, str):
        return None
    if "[" not in dtype and "]" not in dtype and dtype != "ARRAY":
        return None
    if len(dtype) > MAX_NATIVE_TYPE_TEXT:
        _reject(dtype, "data_type", dtype, "native_type_text_limit")
    if dtype.startswith("ARRAY["):
        _reject(dtype, "data_type", dtype, "iec_array_syntax_unobserved", unobserved=True)
    if dtype == "ARRAY":
        _reject(dtype, "dimensions", None, "missing_dimensions")
    if dtype.count("[") > 1 or dtype.count("]") > 1:
        _reject(dtype, "dimensions", dtype[dtype.find("["):],
                "multidimensional_syntax_unobserved", unobserved=True)
    if dtype.count("[") != 1 or dtype.count("]") != 1 or not dtype.endswith("]"):
        _reject(dtype, "data_type", dtype, "invalid_array_syntax")
    element, count = dtype[:-1].split("[", 1)
    if ".." in count:
        _reject(dtype, "dimensions", count, "explicit_bounds_unobserved", unobserved=True)
    parts = count.split(",")
    if len(parts) > 2:
        _reject(dtype, "dimensions", count, "dimension_count_unobserved", unobserved=True)
    if any(re.fullmatch(r"[0-9]+", part) is None or int(part) <= 0 for part in parts):
        _reject(dtype, "dimensions", count, "expected_positive_integer")
    string_element = scalar_descriptor(element) if element == "STRING" or element.startswith("STRING<") else None
    if element == "STRING" or element.startswith("STRING<"):
        if string_element is None or string_element.code != 2048:
            _reject(dtype, "element_type", element, "invalid_string_element_descriptor")
        # Independent normal FB ARRAY save: bare STRING uses capacity 128,
        # displays STRING[n], and saves explicit STRING<128>[n] native text.
        element = string_element.canonical
    if element == "ARRAY":
        _reject(dtype, "element_type", element, "nested_array_profile_unobserved", unobserved=True)
    if string_element is None and not element.isidentifier():
        _reject(dtype, "element_type", element, "unobserved_element_expression", unobserved=True)
    dimensions = tuple(int(part) for part in parts)
    canonical = "{}[{}]".format(element, ",".join(map(str, dimensions)))
    if len(canonical) > MAX_NATIVE_TYPE_TEXT:
        _reject(dtype, "data_type", canonical, "native_type_text_limit")
    return ArrayDescriptor(element, dimensions, canonical, canonical)


def from_gvt_row(row):
    """Decode only observed native GVT ARRAY identity; no allocation/defaults.

    The saved one/two-dimensional prefix/trailer is independent of the FB
    type CString. Unknown trailer values remain explicit format diagnostics,
    not inferred dimensions or a new eligibility rule for unrelated records.
    """
    if getattr(row, "type_code", None) != 128:
        return None
    metadata = row.metadata
    prefix = metadata.get("array_descriptor_raw")
    trailer = metadata.get("array_trailer_raw")
    dtype = row.type_text or "ARRAY"
    if (not isinstance(prefix, (list, tuple)) or len(prefix) != 3
            or any(type(value) is not int for value in prefix)
            or prefix[0] != 128 or not 1 <= prefix[2] <= 0xFFFFFFFF):
        _reject(dtype, "array_descriptor_raw", prefix, "gvt_array_descriptor_unobserved", unobserved=True)
    if (not isinstance(trailer, (list, tuple)) or len(trailer) != 3
            or any(type(value) is not int for value in trailer)):
        _reject(dtype, "array_trailer_raw", trailer, "gvt_array_trailer_unobserved", unobserved=True)
    if list(trailer) == [0, 1, 1]:
        dimensions = (prefix[2],)
    elif trailer[0] == 1 and all(1 <= n <= 0xFFFFFFFF for n in trailer[1:]):
        if trailer[1] * trailer[2] != prefix[2]:
            _reject(dtype, "array_descriptor_raw", prefix, "gvt_array_total_differs_from_dimensions", unobserved=True)
        dimensions = tuple(trailer[1:])
    else:
        _reject(dtype, "array_trailer_raw", trailer, "gvt_array_trailer_unobserved", unobserved=True)
    primitive = {1: "BOOL", 4: "INT", 16: "DINT", 32: "REAL", 8192: "BYTE", 4096: "IP"}
    if prefix[1] in primitive:
        if row.type_text != "":
            _reject(dtype, "type_text_raw", row.type_text, "gvt_primitive_array_text_unobserved", unobserved=True)
        element = primitive[prefix[1]]
    elif prefix[1] == 64:
        if not isinstance(row.type_text, str) or not row.type_text.isidentifier():
            _reject(dtype, "type_text_raw", row.type_text, "gvt_named_array_element_unobserved", unobserved=True)
        if scalar_descriptor(row.type_text) is not None or row.type_text == "ARRAY":
            _reject(dtype, "type_text_raw", row.type_text, "gvt_named_array_scalar_code_conflict", unobserved=True)
        element = row.type_text
    elif prefix[1] == 2048:
        string = scalar_descriptor(row.type_text)
        if string is None or string.code != 2048 or string.canonical != row.type_text:
            _reject(dtype, "type_text_raw", row.type_text, "gvt_array_string_capacity_unobserved", unobserved=True)
        element = string.canonical
    else:
        _reject(dtype, "array_descriptor_raw", prefix, "gvt_array_element_unobserved", unobserved=True)
    return descriptor("{}[{}]".format(element, ",".join(map(str, dimensions))))


def structure_element(name, definitions):
    """Require exact root STRU bytes supplied/frozen by the workflow.

    Native records here need a structure identity, not proof of every nested
    member's business semantics. No dependent defaults are synthesized.
    """
    from autoshop_bridge.formats import tables

    if not isinstance(definitions, dict):
        raise BridgeError("ARRAY structure definitions must be an exact name/bytes mapping.")
    raw = definitions.get(name)
    if not isinstance(raw, bytes):
        raise FormatRejection(
            "Named ARRAY element requires an exact supplied native structure definition.",
            code="offline_array_profile_unobserved",
            context=dict(stage="array_element_definition", field="element_type", value=name,
                         reason="exact_structure_definition_required", definition_supplied=name in definitions),
        )
    try:
        definition = tables.parse(raw, "stru")
    except BridgeError as exc:
        raise FormatRejection(str(exc), code="offline_array_profile_unobserved",
            context=dict(stage="array_element_definition", field="element_type", value=name,
                         reason="native_structure_profile_unobserved", definition_supplied=True)) from exc
    if definition.name != name:
        raise FormatRejection("ARRAY element and native structure identity differ.",
            code="offline_array_profile_unobserved",
            context=dict(stage="array_element_definition", field="element_type", value=name,
                         native_name=definition.name, reason="nonexact_structure_identity", definition_supplied=True))
    return definition
