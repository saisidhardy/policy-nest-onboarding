"""Deterministic 8-tier Indian name matching, PAN/bank format checks, and cross-document consistency."""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from app.models import Application
from app.services.ocr_pipeline import normalize_date_str, normalize_person_name

PAN_STRICT_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_STRICT_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


@dataclass(frozen=True)
class NameMatchResult:
    tier: int
    category: str
    verdict: str  # MATCH | NEEDS_INFO | HUMAN_REVIEW
    reason_code: str | None
    confidence: float
    explanation: str


@dataclass(frozen=True)
class CheckOutcome:
    check_type: str
    target_doc_type: str | None
    status: str  # PASSED | WARN | NEEDS_INFO | FAILED
    origin: str
    confidence: float | None
    details: dict
    explanation: str


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _phonetic_key(token: str) -> str:
    s = token.upper()
    for src, dst in (
        ("PH", "F"),
        ("KS", "X"),
        ("SH", "S"),
        ("TH", "T"),
        ("BH", "B"),
        ("DH", "D"),
        ("KH", "K"),
        ("GH", "G"),
        ("OO", "U"),
        ("EE", "I"),
        ("AA", "A"),
        ("Y", "I"),
        ("W", "V"),
        ("Z", "S"),
    ):
        s = s.replace(src, dst)
    # Collapse repeated characters and remove trailing silent vowels for Indian spelling variants
    dedup = []
    for ch in s:
        if not dedup or dedup[-1] != ch:
            dedup.append(ch)
    res = "".join(dedup)
    if len(res) > 3:
        res = res[0] + re.sub(r"[AEIOU]", "", res[1:])
    return res


def _is_order_preserving_subsequence(shorter: list[str], longer: list[str]) -> bool:
    it = iter(longer)
    return all(tok in it for tok in shorter)


def _initials_match(tokens_a: list[str], tokens_b: list[str]) -> bool:
    if len(tokens_a) < 2 or len(tokens_b) < 2 or len(tokens_a) != len(tokens_b):
        return False
    # Last token (surname) must match or nearly match; earlier tokens can match initial
    if tokens_a[-1] != tokens_b[-1]:
        return False
    has_initial = False
    for ta, tb in zip(tokens_a[:-1], tokens_b[:-1], strict=True):
        if ta == tb:
            continue
        if len(ta) == 1 and tb.startswith(ta):
            has_initial = True
        elif len(tb) == 1 and ta.startswith(tb):
            has_initial = True
        else:
            return False
    return has_initial


def match_indian_names(
    anchor_raw: str | None,
    candidate_raw: str | None,
    *,
    allow_bank_truncation: bool = False,
) -> NameMatchResult:
    """Apply PolicyNest Rulebook v3.2 §5 8-tier Indian name matching."""
    a = normalize_person_name(anchor_raw)
    b = normalize_person_name(candidate_raw)
    if not a or not b:
        return NameMatchResult(
            tier=7,
            category="MISSING_NAME",
            verdict="NEEDS_INFO",
            reason_code="REVIEWER_DISCRETION",
            confidence=0.0,
            explanation="Name missing on one of the compared sources.",
        )

    if a == b:
        return NameMatchResult(1, "EXACT", "MATCH", None, 1.0, f"Exact match: '{a}'.")

    ta = a.split()
    tb = b.split()

    if _initials_match(ta, tb):
        return NameMatchResult(2, "INITIALS", "MATCH", None, 0.90, f"Initials match between '{a}' and '{b}'.")

    if Counter(ta) == Counter(tb):
        return NameMatchResult(
            3, "ORDER_SWAPPED", "MATCH", None, 0.94, f"Reordered token match between '{a}' and '{b}'."
        )

    # Tier 4: Middle name added/omitted preserving order (e.g. RAHUL KUMAR SHARMA <-> RAHUL SHARMA)
    if len(ta) >= 2 and len(tb) >= 2:
        shorter, longer = (ta, tb) if len(ta) < len(tb) else (tb, ta)
        if shorter[0] == longer[0] and shorter[-1] == longer[-1] and _is_order_preserving_subsequence(shorter, longer):
            return NameMatchResult(
                4, "MIDDLE_NAME_DELTA", "MATCH", None, 0.88, f"Middle name delta between '{a}' and '{b}'."
            )

    # Tier 8: Banking CBS truncation / prefix match
    if allow_bank_truncation and ta[-1] == tb[-1] and ta[0][0] == tb[0][0]:
        if len(b) >= 6 and (a.startswith(b[:6]) or (len(tb) >= 2 and all(len(t) == 1 for t in tb[:-1]))):
            return NameMatchResult(
                8, "BANKING_TRUNCATION", "MATCH", None, 0.85, f"Bank truncated name match: '{a}' vs '{b}'."
            )

    # Tier 5: Spelling / phonetic variant when surname matches or edit distance small
    if len(ta) == len(tb) and all(
        (_levenshtein(x, y) <= 2 or _phonetic_key(x) == _phonetic_key(y)) for x, y in zip(ta, tb, strict=True)
    ):
        return NameMatchResult(
            5,
            "SPELLING_VARIANT",
            "NEEDS_INFO",
            "NAME_SPELLING_VARIANT",
            0.78,
            f"Minor spelling/phonetic variation between '{a}' and '{b}'. Requires applicant or reviewer confirmation.",
        )

    # Tier 6: Given name matches closely, surname differs (post-marriage surname change)
    if len(ta) >= 2 and len(tb) >= 2 and (ta[0] == tb[0] or _levenshtein(ta[0], tb[0]) <= 1) and ta[-1] != tb[-1]:
        return NameMatchResult(
            6,
            "MARRIAGE_SURNAME_CHANGE",
            "NEEDS_INFO",
            "REVIEWER_DISCRETION",
            0.65,
            f"Given name matches ('{ta[0]}') while surname differs ('{ta[-1]}' vs '{tb[-1]}'). Route to human review.",
        )

    # Tier 7: Unrelated person -> NEVER auto-reject; route to human review
    return NameMatchResult(
        7,
        "DIFFERENT_PERSON",
        "HUMAN_REVIEW",
        "NAME_MISMATCH",
        0.15,
        f"Significant name divergence ('{a}' vs '{b}'). Flagged for mandatory human review (never auto-rejected).",
    )


def validate_pan_format(pan: str | None) -> CheckOutcome:
    if not pan:
        return CheckOutcome(
            "PAN_FORMAT", "PAN_CARD", "NEEDS_INFO", "DETERMINISTIC_RULE", 0.0, {}, "PAN number not yet available."
        )
    cleaned = pan.strip().upper()
    if not PAN_STRICT_RE.match(cleaned):
        return CheckOutcome(
            "PAN_FORMAT",
            "PAN_CARD",
            "FAILED",
            "DETERMINISTIC_RULE",
            1.0,
            {
                "pan_masked": f"{cleaned[:2]}***{cleaned[-2:]}" if len(cleaned) >= 4 else "***",
                "reason_code": "PAN_FORMAT_INVALID",
            },
            "PAN does not match AAAAA9999A format.",
        )
    if cleaned[3] != "P":
        return CheckOutcome(
            "PAN_FORMAT",
            "PAN_CARD",
            "FAILED",
            "DETERMINISTIC_RULE",
            1.0,
            {"holder_type": cleaned[3], "reason_code": "PAN_NOT_INDIVIDUAL"},
            f"PAN 4th character is '{cleaned[3]}'; only Individual ('P') PANs are eligible for POSP onboarding.",
        )
    return CheckOutcome(
        "PAN_FORMAT",
        "PAN_CARD",
        "PASSED",
        "DETERMINISTIC_RULE",
        1.0,
        {"holder_type": "P"},
        "PAN format and individual holder code ('P') verified.",
    )


def compare_dob_values(anchor_dob: str | None, candidate_dob: str | None, source_label: str) -> CheckOutcome:
    if not anchor_dob or not candidate_dob:
        return CheckOutcome(
            "CROSS_DOC_DOB",
            source_label,
            "WARN",
            "DETERMINISTIC_RULE",
            None,
            {"anchor_dob": anchor_dob, "candidate_dob": candidate_dob},
            f"Date of birth could not be extracted from {source_label} for cross-check.",
        )
    a = normalize_date_str(anchor_dob) or anchor_dob
    b = normalize_date_str(candidate_dob) or candidate_dob
    if a == b:
        return CheckOutcome(
            "CROSS_DOC_DOB",
            source_label,
            "PASSED",
            "DETERMINISTIC_RULE",
            1.0,
            {"anchor_dob": a, "candidate_dob": b},
            f"Date of birth matches anchor ({a}).",
        )
    # Year-only Aadhaar tolerance per Rulebook v3.2 §4.3
    if source_label == "AADHAAR_FRONT" and len(b) == 4 and a.startswith(b):
        return CheckOutcome(
            "CROSS_DOC_DOB",
            source_label,
            "PASSED",
            "DETERMINISTIC_RULE",
            0.9,
            {"anchor_dob": a, "candidate_dob": b, "year_only_match": True},
            f"Aadhaar year of birth ({b}) matches anchor birth year.",
        )
    return CheckOutcome(
        "CROSS_DOC_DOB",
        source_label,
        "NEEDS_INFO",
        "DETERMINISTIC_RULE",
        0.95,
        {"anchor_dob": a, "candidate_dob": b, "reason_code": "DOB_MISMATCH"},
        f"Date of birth mismatch between anchor ({a}) and {source_label} ({b}).",
    )


def evaluate_cross_document_consistency(app: Application, effective_by_type: dict[str, dict]) -> list[CheckOutcome]:
    """Run deterministic PAN format, bank format, and cross-document name/DOB comparisons."""
    outcomes: list[CheckOutcome] = []

    pan_fields = effective_by_type.get("PAN_CARD", {})
    pan_to_check = pan_fields.get("pan_number") or app.pan_number
    outcomes.append(validate_pan_format(pan_to_check))

    if (
        app.pan_number
        and pan_fields.get("pan_number")
        and app.pan_number.upper() != str(pan_fields["pan_number"]).upper()
    ):
        outcomes.append(
            CheckOutcome(
                "CROSS_DOC_PAN_MATCH",
                "PAN_CARD",
                "WARN",
                "DETERMINISTIC_RULE",
                0.9,
                {"declared_pan": app.pan_number, "extracted_pan": pan_fields["pan_number"]},
                "Declared PAN differs from OCR-extracted PAN; reviewer confirmation recommended.",
            )
        )

    anchor_name = pan_fields.get("full_name") or app.full_name
    anchor_dob = pan_fields.get("dob") or (app.date_of_birth.isoformat() if app.date_of_birth else None)

    # Check age >= 18 against anchor DOB
    if anchor_dob and len(anchor_dob) == 10:
        try:
            dob_dt = date.fromisoformat(anchor_dob)
            ref_dt = app.created_at.date()
            age_years = ref_dt.year - dob_dt.year - ((ref_dt.month, ref_dt.day) < (dob_dt.month, dob_dt.day))
            outcomes.append(
                CheckOutcome(
                    "ELIGIBILITY_AGE",
                    "PAN_CARD",
                    "PASSED" if age_years >= 18 else "FAILED",
                    "DETERMINISTIC_RULE",
                    1.0,
                    {"age_years": age_years},
                    f"Applicant age at application start is {age_years} years."
                    if age_years >= 18
                    else f"Applicant age ({age_years}) is below the statutory minimum of 18 years (UNDERAGE).",
                )
            )
        except ValueError:
            pass

    for doc_type in ("PAN_CARD", "AADHAAR_FRONT", "CLASS_10_MARKSHEET"):
        fields = effective_by_type.get(doc_type, {})
        if not fields:
            continue
        if doc_type != "PAN_CARD" or (app.full_name and fields.get("full_name")):
            target_name = fields.get("full_name")
            if target_name and anchor_name:
                nm = match_indian_names(anchor_name, target_name)
                st = "PASSED" if nm.verdict == "MATCH" else ("NEEDS_INFO" if nm.verdict == "NEEDS_INFO" else "WARN")
                outcomes.append(
                    CheckOutcome(
                        "CROSS_DOC_NAME",
                        doc_type,
                        st,
                        "DETERMINISTIC_RULE",
                        nm.confidence,
                        {
                            "tier": nm.tier,
                            "category": nm.category,
                            "reason_code": nm.reason_code,
                            "anchor": anchor_name,
                            "candidate": target_name,
                        },
                        nm.explanation,
                    )
                )
        if doc_type != "PAN_CARD":
            outcomes.append(compare_dob_values(anchor_dob, fields.get("dob"), doc_type))

    # Bank format and holder name comparison
    bank_fields = effective_by_type.get("BANK_DOCUMENT", {})
    ifsc_to_check = bank_fields.get("ifsc_code") or app.ifsc_code
    if ifsc_to_check and IFSC_STRICT_RE.match(str(ifsc_to_check).upper()):
        outcomes.append(
            CheckOutcome(
                "BANK_FORMAT_IFSC",
                "BANK_DOCUMENT",
                "PASSED",
                "DETERMINISTIC_RULE",
                1.0,
                {"ifsc_code": str(ifsc_to_check).upper()},
                f"IFSC code {str(ifsc_to_check).upper()} matches RBI format.",
            )
        )
    else:
        outcomes.append(
            CheckOutcome(
                "BANK_FORMAT_IFSC",
                "BANK_DOCUMENT",
                "NEEDS_INFO",
                "DETERMINISTIC_RULE",
                0.0,
                {"ifsc_code": ifsc_to_check},
                "Valid 11-character IFSC code missing or invalid.",
            )
        )

    holder_to_check = bank_fields.get("full_name") or app.account_holder_name
    if anchor_name and holder_to_check:
        nm_bank = match_indian_names(anchor_name, holder_to_check, allow_bank_truncation=True)
        outcomes.append(
            CheckOutcome(
                "BANK_HOLDER_NAME",
                "BANK_DOCUMENT",
                "PASSED" if nm_bank.verdict == "MATCH" else "NEEDS_INFO",
                "DETERMINISTIC_RULE",
                nm_bank.confidence,
                {"tier": nm_bank.tier, "category": nm_bank.category, "anchor": anchor_name, "holder": holder_to_check},
                nm_bank.explanation,
            )
        )

    return outcomes
