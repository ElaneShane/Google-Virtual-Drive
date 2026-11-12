# Old class name -> merged class name (Run G).
RENAME = {
    "NP (Symb) Street Cleaning FRI 10AM - 12PM -- 7026": "Street Cleaning Symbol",
    "NP (Symb) Street Cleaning MON": "Street Cleaning Symbol",
    "NP (Symb) Street Cleaning THU": "Street Cleaning Symbol",
    "NP (Symb) Street Cleaning TUE": "Street Cleaning Symbol",
    "NP (Symb) Street Cleaning WED 10AM - 12PM -- 7016": "Street Cleaning Symbol",
    "NP Street Cleaning MON": "Street Cleaning Text",
    "NP Street Cleaning TUE": "Street Cleaning Text",
    "Speed Humps": "Speed Hump Sign",
    "Speed humps -- W17-1": "Speed Hump Sign",
    "Bump": "Speed Hump Sign",
    "Bumps": "Speed Hump Sign",
    "Bumps -- 0325": "Speed Hump Sign",
    "Bike Green Sign 4280": "Bike Lane Sign",
    "Bike Full Lane": "Bike Lane Sign",
    "Bus/Bike Sign": "Bike Lane Sign",
    "Yield Here, Left Arrow 1521": "Yield Here to Pedestrians",
    "Yield Here, Right Arrow 1522": "Yield Here to Pedestrians",
    "Pedestrian Crossing with Crosswalk Lines, (Symbol) 570": "Pedestrian Traffic, (Symbol) 572",
}
DROPPED = ["dnsot_sign"]            # zero boxes anywhere
EXTRA = ["R4-7 Keep Right Arrow"]   # new class, comes from ARTS only


def build_new_names(old_names, rename=RENAME, dropped=DROPPED, extra=EXTRA):
    """The Run G class list: old names that stay (old order), then merged names, then new ones."""
    for n in list(rename) + list(dropped):
        if n not in old_names:
            raise ValueError(f"name not in the old class list: {n}")
    new = [n for n in old_names if n not in rename and n not in dropped]
    for target in rename.values():
        if target not in new:
            new.append(target)
    for n in extra:
        if n not in new:
            new.append(n)
    return new