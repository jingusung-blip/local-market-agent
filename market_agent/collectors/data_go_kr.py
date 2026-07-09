from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


class DataGoKrApiError(RuntimeError):
    """Raised for any data.go.kr Open API response that isn't a success.

    Shared by every data.go.kr-backed collector (MOLIT 매매, MOLIT 전월세, ...)
    so that a bug fix here (e.g. the resultCode-width issue found in the
    매매 실거래가 API) automatically applies everywhere instead of needing to
    be re-discovered and re-fixed per collector.
    """


def parse_xml_items(payload: bytes, item_path: str = "./body/items/item") -> list[dict[str, Any]]:
    """Parse a data.go.kr XML response into a list of flat field dicts.

    Handles the header/resultCode success check generically. Different
    data.go.kr services are inconsistent about the width of their success
    code ("00" vs "000"), so any all-zero code is treated as success rather
    than hardcoding one length (this was a real bug in the 매매 실거래가 API).
    """
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise DataGoKrApiError(f"data.go.kr API returned an unparseable response: {exc}") from exc

    header = root.find("header")
    if header is not None:
        result_code = (header.findtext("resultCode") or "").strip()
        if result_code and set(result_code) != {"0"}:
            raise DataGoKrApiError(
                f"data.go.kr API error {result_code}: {header.findtext('resultMsg')}"
            )

    items: list[dict[str, Any]] = []
    for item in root.findall(item_path):
        record = {child.tag: (child.text or "").strip() for child in item}
        items.append(record)
    return items
