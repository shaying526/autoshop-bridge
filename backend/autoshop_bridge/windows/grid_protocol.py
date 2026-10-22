"""Validate the declaration-only MSAA snapshot before exposing any rows."""

from autoshop_bridge.errors import BridgeError


def unpack_grid(value):
    if (
        not isinstance(value, dict)
        or value.get("schema") != 2
        or not isinstance(value.get("rows"), list)
        or not isinstance(value.get("metadata"), dict)
    ):
        raise BridgeError("Unsupported accessibility grid response.")
    rows, meta = value["rows"], value["metadata"]
    if (
        meta.get("read_scope") != "declarations"
        or type(meta.get("declaration_rows")) is not int
        or meta["declaration_rows"] != len(rows)
        or not 0 <= len(rows) <= 4096
        or type(meta.get("accessible_children")) is not int
        or type(meta.get("physical_rows")) is not int
        or type(meta.get("expanded_monitor_rows")) is not int
        or type(meta.get("watch_joined_by_name")) is not bool
        or type(meta.get("elapsed_ms")) is not int
        or meta["elapsed_ms"] < 0
        or not len(rows) + 2
        <= meta["physical_rows"]
        <= meta["accessible_children"]
        <= 10000
        or meta["expanded_monitor_rows"] != meta["physical_rows"] - len(rows) - 2
    ):
        raise BridgeError("Incomplete/inconsistent accessibility grid metadata.")
    keys = None
    for row in rows:
        if (
            not isinstance(row, dict)
            or not row
            or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in row.items()
            )
        ):
            raise BridgeError("Invalid accessibility grid row.")
        if keys is None:
            keys = set(row)
        elif set(row) != keys:
            raise BridgeError("Accessibility grid row columns differ.")
    return rows, meta
