
import csv
import re


# Run G name -> name used in the class map.
ALIASES = {
    "Stop Ahead": "STOP AHEAD SYMBOL W3-1",
    "R4-7 Keep Right Arrow": "r4-7(island nose-right)",
    "Right Lane Must Turn Right": "Must Turn Right (Text)",
    "Speed Hump Sign": "Speed Humps",
}


LOOKUP_FIELDS = [
    "ladot_name",
    "stock_number",
    "mutcd_code",
    "catalog_description",
    "status",
    "candidates",
    "note",
]


def clean(text):
    return re.sub(
        r"\s+", " ", "" if text is None else str(text)
    ).strip()


def norm_number(text):
    """316 -> 0316; preserve alphanumeric stock numbers."""
    s = clean(text)
    return s.zfill(4) if s.isdigit() else s


def _stock_tokens(text):
    """Read stock numbers separated by pipes or spaces."""
    raw = clean(text)
    if not raw:
        return []

    parts = raw.split("|") if "|" in raw else raw.split()

    result = []
    for part in parts:
        number = norm_number(part)
        if number and number not in result:
            result.append(number)

    return result


def catalog_index(catalog):
    index = {}

    for row in catalog:
        index.setdefault(row["sign_number"], []).append(row)

    return index


def describe(number, index):
    """Return a stock number and its catalog description."""
    rows = index.get(number)

    if not rows:
        return f"{number} (not in master catalog)"

    descriptions = []
    for row in rows:
        description = clean(row.get("description"))
        if description and description not in descriptions:
            descriptions.append(description)

    if descriptions:
        return f"{number} {' / '.join(descriptions)}"

    return number


def _candidate_numbers_from_catalog_text(text):
    """Extract stock numbers from audit candidate text such as:
    1410 description || 1420 description
    """
    numbers = []

    for part in clean(text).split("||"):
        match = re.match(r"^\s*([A-Za-z0-9-]+)\s+", part)
        if match:
            number = norm_number(match.group(1))
            if number not in numbers:
                numbers.append(number)

    return numbers


def _candidate_text(numbers, index):
    return "; ".join(describe(number, index) for number in numbers)


def build_lookup(map_rows, class_names, index):
    """Build one lookup row per detector class.

    The v3 mapping_status field controls whether a stock number is:
    - filled automatically
    - suggested for review
    - shown as multiple options
    - deliberately left blank
    """

    by_name = {
        clean(row["detector_class"]): row
        for row in map_rows
    }

    out = []

    for name in class_names:
        entry = {field: "" for field in LOOKUP_FIELDS}
        entry["ladot_name"] = name

        map_name = ALIASES.get(name, name)
        row = by_name.get(map_name)

        if row is None:
            entry["status"] = "not in class map"
            out.append(entry)
            continue

        mapping_status = clean(row.get("mapping_status"))
        stock_numbers = _stock_tokens(row.get("stock_examples"))
        mutcd = clean(row.get("mutcd"))
        note = clean(row.get("note"))
        instructions = clean(row.get("review_instructions"))

        # Preserve MUTCD information even when stock is blank.
        entry["mutcd_code"] = mutcd
        entry["note"] = note or instructions

        # Confirmed single-stock mappings.
        if mapping_status in {
            "confirmed",
            "confirmed_no_mutcd",
            "confirmed_user_decision",
        }:
            if len(stock_numbers) != 1:
                entry["status"] = (
                    "class map warning: expected one stock number"
                )
                out.append(entry)
                continue

            number = stock_numbers[0]
            entry["stock_number"] = number

            hit = index.get(number)

            if hit:
                entry["catalog_description"] = clean(
                    hit[0].get("description")
                )
                if not entry["mutcd_code"]:
                    entry["mutcd_code"] = clean(
                        hit[0].get("mutcd_code")
                    )
                entry["status"] = "matched in master catalog"
            else:
                entry["catalog_description"] = clean(
                    row.get("catalog_description")
                )
                entry["status"] = "stock number not in master catalog"

        # A suggested default that must still be checked.
        elif mapping_status == "assumed_review":
            if len(stock_numbers) == 1:
                number = stock_numbers[0]
                entry["stock_number"] = number

                hit = index.get(number)
                if hit:
                    entry["catalog_description"] = clean(
                        hit[0].get("description")
                    )
                    if not entry["mutcd_code"]:
                        entry["mutcd_code"] = clean(
                            hit[0].get("mutcd_code")
                        )

            entry["status"] = "assumed - review"

        # One stock number exists, but formatting needs checking.
        elif mapping_status == "confirmed_format_review":
            entry["candidates"] = _candidate_text(
                stock_numbers, index
            )
            entry["status"] = "format verification required"

        # Several possible stock numbers: reviewer chooses from frame.
        elif mapping_status == "options_for_frame_review":
            entry["candidates"] = _candidate_text(
                stock_numbers, index
            )
            entry["status"] = "options - review frame"

        # Schedule or printed text determines the stock number.
        elif mapping_status in {
            "schedule_review_no_stock",
            "frame_text_review_no_stock",
            "no_catalog_match_blank",
        }:
            entry["status"] = mapping_status

        # Unresolved classes: show known suggestions, but don't select one.
        elif mapping_status == "unresolved":
            numbers = stock_numbers

            if not numbers:
                numbers = _candidate_numbers_from_catalog_text(
                    row.get("catalog_candidates")
                )

            entry["candidates"] = _candidate_text(numbers, index)
            entry["status"] = "unresolved - human review"

        else:
            entry["status"] = (
                f"unrecognized mapping status: {mapping_status}"
            )

        out.append(entry)

    return out


def write_lookup(entries, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=LOOKUP_FIELDS
        )
        writer.writeheader()
        writer.writerows(entries)


def read_lookup(path):
    """Lookup file -> {class name: row}."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {
            row["ladot_name"]: row
            for row in csv.DictReader(f)
        }


def catalog_text(entry):
    """Plain-English text for the Catalog match column in review.xlsx."""
    if not entry:
        return ""

    stock = (entry.get("stock_number") or "").strip()
    description = clean(entry.get("catalog_description", "") or "")
    status = (entry.get("status") or "").lower()
    candidates = (entry.get("candidates") or "").strip()

    # One stock number picked for this sign
    if stock:
        text = clean(f"{stock} {description}")
        if "assumed" in status:
            return f"{text} (best guess, please confirm)"
        return text

    # Several possible numbers: the reviewer chooses by looking at the sign
    if candidates:
        candidates = candidates.replace(" (not in master catalog)", "")
        return f"Pick one: {candidates}"

    # No number, because it depends on text printed on the sign
    if "schedule" in status or "text" in status:
        return "Type the stock number yourself (it depends on the text on the sign)"

    # Nothing in the catalog for this sign type
    return "No stock number found. Type it in if you know it."