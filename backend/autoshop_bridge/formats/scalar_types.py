"""Pure native scalar descriptors, separate from container record profiles.

Recognition does not prove that a particular container or PLC supports a type
or capacity. Those codecs and the IDE/compiler retain their own responsibilities.
"""

from dataclasses import dataclass
import re
from typing import Optional


_PRIMITIVE_CODES = {"BOOL": 1, "INT": 4, "DINT": 16, "REAL": 32}
STRING_DEFAULT_LENGTH = 128  # Normal V4.11.0.5 Define String dialog, 2026-10-29.
MAX_NATIVE_TYPE_TEXT = 512  # Existing FB/FC/STRU record reader boundary.


@dataclass(frozen=True)
class ScalarDescriptor:
    code: int
    type_text: str
    canonical: str
    string_length: Optional[int]


def descriptor(dtype):
    """Return an explicit scalar identity, or None for named/unknown types.

    STRING length is part of its native type text, not an ARRAY descriptor or
    a project structure name. Bare STRING uses the observed IDE dialog default;
    no unmeasured maximum PLC string capacity is imposed here.
    """
    if not isinstance(dtype, str):
        return None
    code = _PRIMITIVE_CODES.get(dtype)
    if code is not None:
        return ScalarDescriptor(code, "", dtype, None)
    if dtype == "STRING":
        length = STRING_DEFAULT_LENGTH
    else:
        if len(dtype) > MAX_NATIVE_TYPE_TEXT:
            return None
        match = re.fullmatch(r"STRING<([0-9]+)>", dtype)
        if match is None:
            return None
        length = int(match.group(1))
        if length <= 0:
            return None
    canonical = "STRING<{}>".format(length)
    return ScalarDescriptor(2048, canonical, canonical, length)
