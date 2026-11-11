"""Indian states and union territories with PolicyNest operational region mapping."""

INDIAN_STATE_TO_REGION: dict[str, str] = {
    # NORTH
    "Chandigarh": "NORTH",
    "Delhi": "NORTH",
    "Haryana": "NORTH",
    "Himachal Pradesh": "NORTH",
    "Jammu and Kashmir": "NORTH",
    "Ladakh": "NORTH",
    "Punjab": "NORTH",
    "Rajasthan": "NORTH",
    "Uttar Pradesh": "NORTH",
    "Uttarakhand": "NORTH",
    # SOUTH
    "Andaman and Nicobar Islands": "SOUTH",
    "Andhra Pradesh": "SOUTH",
    "Karnataka": "SOUTH",
    "Kerala": "SOUTH",
    "Lakshadweep": "SOUTH",
    "Puducherry": "SOUTH",
    "Tamil Nadu": "SOUTH",
    "Telangana": "SOUTH",
    # EAST
    "Arunachal Pradesh": "EAST",
    "Assam": "EAST",
    "Bihar": "EAST",
    "Jharkhand": "EAST",
    "Manipur": "EAST",
    "Meghalaya": "EAST",
    "Mizoram": "EAST",
    "Nagaland": "EAST",
    "Odisha": "EAST",
    "Sikkim": "EAST",
    "Tripura": "EAST",
    "West Bengal": "EAST",
    # WEST
    "Chhattisgarh": "WEST",
    "Dadra and Nagar Haveli and Daman and Diu": "WEST",
    "Goa": "WEST",
    "Gujarat": "WEST",
    "Madhya Pradesh": "WEST",
    "Maharashtra": "WEST",
}

INDIAN_STATES = sorted(INDIAN_STATE_TO_REGION.keys())
_CANONICAL_BY_LOWER = {s.lower(): s for s in INDIAN_STATES}


def normalize_indian_state(value: str) -> str:
    cleaned = " ".join(value.split()).strip()
    match = _CANONICAL_BY_LOWER.get(cleaned.lower())
    if not match:
        raise ValueError("Select a valid Indian State or Union Territory.")
    return match


def region_for_state(state: str | None) -> str | None:
    if not state:
        return None
    return INDIAN_STATE_TO_REGION.get(state)
