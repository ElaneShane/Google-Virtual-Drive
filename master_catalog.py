
"""Read only the Main Sign List worksheet from the LADOT master catalog.

The Main Sign List is the source of truth for this lookup.
Other worksheets are deliberately excluded.
"""

import re

MAIN = "Main Sign List"


def _clean(value):
    return re.sub(
        r"\s+", " ", "" if value is None else str(value)
    ).strip()


def _number(value):
    """316 -> 0316; preserve alphanumeric numbers such as 0318-mod."""
    text = _clean(value)

    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]

    return text.zfill(4) if text.isdigit() else text


def _entry(number, mutcd, description, size, source):
    return {
        "sign_number": number,
        "mutcd_code": mutcd,
        "sms_number": "",
        "description": description,
        "size": size,
        "material": "",
        "page": source,
        "flags": "",
    }


def load_master_catalog(path):
    from openpyxl import load_workbook

    wb = load_workbook(
        path, read_only=True, data_only=True
    )

    if MAIN not in wb.sheetnames:
        wb.close()
        raise ValueError(
            f"Required worksheet '{MAIN}' was not found in {path}"
        )

    ws = wb[MAIN]
    rows = ws.iter_rows(values_only=True)

    try:
        headers = [_clean(h) for h in next(rows)]
    except StopIteration:
        wb.close()
        return []

    out = []

    for values in rows:
        d = dict(zip(headers, values))

        number = _number(d.get("STOCK_NUMBER"))
        if not number:
            continue

        out.append(
            _entry(
                number,
                _clean(d.get("MUTCD_CODE")),
                _clean(d.get("DESCRIPTION")),
                _clean(d.get("ALT_DESC")),
                MAIN,
            )
        )

    wb.close()
    return out
