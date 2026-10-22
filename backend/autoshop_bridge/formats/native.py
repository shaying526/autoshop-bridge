"""Explicit dispatch: ST, FB and FC have separate native container profiles."""

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import fb
from autoshop_bridge.formats import st
from autoshop_bridge.formats import fc

PROFILES = {"st": st.PROFILE, "fb": fb.PROFILE, "fc": fc.PROFILE}


def line_metadata_matches(container):
    if isinstance(container, fc.FCContainer):
        return container.line_metadata_matches_source
    return container.line_table_count == container.line_count


def parse(raw: bytes, kind: str):
    if kind == "st":
        return st.parse(raw)
    if kind == "fb":
        return fb.parse(raw)
    if kind == "fc":
        return fc.parse(raw)
    raise BridgeError("Unsupported native kind: {}".format(kind))
