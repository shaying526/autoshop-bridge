"""The observed V4.11.0.5 root-level LiteST registration layout."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import PureWindowsPath

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats import st
from autoshop_bridge.projects.identifiers import require_new_identifier
from autoshop_bridge.projects.inventory import registration

PROFILE = "litest-fb-root-registration-v1"
STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
FIELDS = (
    ("FileType", "81"), ("ProgType", "7"), ("Author", ""), ("Caption", None),
    ("Alias", None), ("CreateTime", None), ("FileName", None), ("LastModifyTime", None),
    ("FileDesc", ""), ("POUID", "-1"), ("Timer", "0"), ("Encrypted", "0"),
    ("SysSTFunc", "0"), ("StbParentID", "0"), ("nStbRow", "-1"), ("nStbCol", "-1"),
)


def add_litest(hcp_raw, folder_raw, name, stamp):
    """Append one HCP row and insert one FB tree entry. Preserve other bytes."""
    require_new_identifier(name)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,126}", name) or PureWindowsPath(name).is_reserved():
        raise BridgeError("Expected a non-device ASCII LiteST FB name.")
    try:
        valid_time = datetime.strptime(stamp, STAMP_FORMAT).strftime(STAMP_FORMAT) == stamp
    except (TypeError, ValueError):
        valid_time = False
    if not valid_time:
        raise BridgeError("Unsupported LiteST registration timestamp.")
    root = registration(hcp_raw)
    rows = root.findall("file")
    decoded = st.decode(hcp_raw)
    tail = "\t</file>\r\n</project>\r\n".encode("utf-16-le")
    if (not decoded.startswith(b"\xff\xfe") or not decoded.endswith(tail)
            or root.attrib or root.findtext("Version") != "1" or not rows
            or [row.attrib for row in rows] != [{"id": str(i)} for i in range(1, len(rows) + 1)]
            or list(root)[-len(rows):] != rows):
        raise BridgeError("Unsupported HCP registration layout for new LiteST FB.")
    known_fb = [r for r in rows if r.findtext("FileType") == "81" and r.findtext("ProgType") == "7"]
    if not any(
        [(x.tag, x.text or "") for x in row if x.tag not in {k for k, v in FIELDS if v is None}]
        == [(k, v) for k, v in FIELDS if v is not None]
        and [x.tag for x in row] == [k for k, _ in FIELDS]
        and not any(x.attrib or len(x) for x in row)
        for row in known_fb
    ):
        raise BridgeError("No observed LiteST FB registration profile in the selected HCP.")
    occupied = {value.casefold() for row in rows for value in
                (row.findtext("Caption") or "", row.findtext("Alias") or "",
                 PureWindowsPath(row.findtext("FileName") or "").stem)}
    if name.casefold() in occupied:
        raise BridgeError("The name already occurs in the HCP registration.")
    file_name = name + ".FB"
    values = {"Caption": name, "Alias": name, "FileName": file_name,
              "CreateTime": stamp, "LastModifyTime": stamp}
    new_id = len(rows) + 1
    row_xml = '\t<file id="{}">\r\n'.format(new_id)
    for key, value in FIELDS:
        row_xml += "\t\t<{0}>{1}</{0}>\r\n".format(key, values[key] if value is None else value)
    row_xml += "\t</file>\r\n"
    end = "</project>\r\n".encode("utf-16-le")
    new_hcp = st.encode(decoded[:-len(end)] + row_xml.encode("utf-16-le") + end)
    reread = registration(new_hcp)
    if ([ET.tostring(n).rstrip() for n in list(reread)[:-1]] != [ET.tostring(n).rstrip() for n in root]
            or reread[-1].findtext("FileName") != file_name):
        raise BridgeError("HCP candidate did not preserve existing registration.")

    root_marker = b"FB\r\nROOT\r\n"
    end_marker = b"FC\r\nROOT\r\n"
    if (not folder_raw.startswith(b"AutoShop\r\n\t1\r\nPROG\r\nROOT\r\n")
            or folder_raw.count(root_marker) != 1 or folder_raw.count(end_marker) != 1):
        raise BridgeError("Unsupported folder.txt root layout.")
    start = folder_raw.index(root_marker) + len(root_marker)
    stop = folder_raw.index(end_marker)
    entries = re.findall(rb"\tFILE\t([A-Za-z_][A-Za-z0-9_]*\.[Ff][Bb])\r\n", folder_raw[start:stop])
    existing = [entry.decode("ascii") for entry in entries]
    registered = [r.findtext("FileName") or "" for r in rows
                  if r.findtext("FileType") in ("45", "81") and r.findtext("ProgType") == "7"]
    if (b"".join(b"\tFILE\t" + entry + b"\r\n" for entry in entries) != folder_raw[start:stop]
            or sorted(existing, key=str.casefold) != existing
            or sorted(existing) != sorted(registered)):
        raise BridgeError("folder.txt FB tree does not match the observed flat HCP registration.")
    offset = start
    for entry in existing:
        if file_name.casefold() < entry.casefold():
            break
        offset += len(b"\tFILE\t\r\n") + len(entry)
    new_folder = folder_raw[:offset] + ("\tFILE\t" + file_name + "\r\n").encode("ascii") + folder_raw[offset:]
    return new_hcp, new_folder, new_id
