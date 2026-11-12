import hashlib
import random

MODULES = {
    "MOTOR": ("Motor insurance fundamentals", 225),
    "HEALTH": ("Health insurance fundamentals", 225),
    "LIFE": ("Life insurance fundamentals", 225),
    "GOVERNANCE": ("Conduct, governance and customer protection", 225),
}

_BASE = [
    (
        "MOTOR",
        "What is the primary purpose of third-party motor cover?",
        [
            "Cover damage to the insured car only",
            "Cover legal liability to third parties",
            "Cover routine servicing",
            "Cover depreciation",
        ],
        1,
    ),
    (
        "MOTOR",
        "Which document normally describes the insured vehicle and cover period?",
        ["Policy schedule", "Bank statement", "Training certificate", "PAN card"],
        0,
    ),
    (
        "MOTOR",
        "What should a seller do before recommending motor cover?",
        [
            "Assume the cheapest is suitable",
            "Identify customer needs and explain exclusions",
            "Promise every claim will be paid",
            "Hide deductibles",
        ],
        1,
    ),
    (
        "MOTOR",
        "A deductible is best described as what?",
        ["A customer share of an admissible claim", "A guaranteed bonus", "A tax refund", "An insurer licence"],
        0,
    ),
    (
        "MOTOR",
        "Why must material vehicle information be accurate?",
        [
            "It has no effect",
            "It supports fair underwriting and claim handling",
            "It replaces KYC",
            "It guarantees renewal",
        ],
        1,
    ),
    (
        "HEALTH",
        "What is a waiting period?",
        [
            "Time before specified cover becomes available",
            "Time to print a card",
            "A premium holiday",
            "A claim guarantee",
        ],
        0,
    ),
    (
        "HEALTH",
        "What is the responsible way to discuss exclusions?",
        [
            "Do not mention them",
            "Explain material exclusions before purchase",
            "Say all treatments are covered",
            "Discuss only after a claim",
        ],
        1,
    ),
    (
        "HEALTH",
        "Cashless treatment generally depends on what?",
        ["Network and authorization conditions", "A verbal promise", "PAN type", "Vehicle age"],
        0,
    ),
    (
        "HEALTH",
        "Why should pre-existing conditions be disclosed accurately?",
        [
            "For appropriate underwriting and claim assessment",
            "Only for marketing",
            "They are never relevant",
            "To waive every waiting period",
        ],
        0,
    ),
    (
        "HEALTH",
        "What does sum insured represent?",
        [
            "The applicable cover limit, subject to terms",
            "A guaranteed investment return",
            "The agent commission",
            "A hospital discount",
        ],
        0,
    ),
    (
        "LIFE",
        "Why is nomination recorded?",
        [
            "To identify a recipient under policy rules",
            "To set interest rates",
            "To replace underwriting",
            "To waive premiums",
        ],
        0,
    ),
    (
        "LIFE",
        "What is the correct approach to benefit illustrations?",
        [
            "Present assumptions and limitations clearly",
            "Guarantee every illustrated value",
            "Hide charges",
            "Change figures verbally",
        ],
        0,
    ),
    (
        "LIFE",
        "A term insurance plan primarily provides what?",
        ["Life cover for a stated term", "Hospital network access", "Vehicle repairs", "A bank account"],
        0,
    ),
    (
        "LIFE",
        "Why should affordability be considered?",
        [
            "To support suitable, sustainable recommendations",
            "To maximize premium regardless of need",
            "It is irrelevant",
            "To avoid disclosures",
        ],
        0,
    ),
    (
        "LIFE",
        "What should be done when a customer does not understand a feature?",
        [
            "Explain it in clear language before proceeding",
            "Ask for an immediate signature",
            "Omit the feature",
            "Promise a claim",
        ],
        0,
    ),
    (
        "GOVERNANCE",
        "What is the proper treatment of customer personal data?",
        [
            "Use only for authorized purposes and protect it",
            "Share it freely",
            "Post it publicly",
            "Retain it without controls",
        ],
        0,
    ),
    (
        "GOVERNANCE",
        "What must happen when an answer is unknown?",
        ["Escalate or verify rather than invent", "Guess confidently", "Change the question", "Promise approval"],
        0,
    ),
    (
        "GOVERNANCE",
        "Which statement about claims is appropriate?",
        [
            "Claims are assessed under policy terms",
            "Every claim is guaranteed",
            "Agents decide all claims",
            "Documents are unnecessary",
        ],
        0,
    ),
    (
        "GOVERNANCE",
        "What is a conflict of interest?",
        [
            "A competing interest that may affect impartial advice",
            "A policy schedule",
            "A training module",
            "A claim form",
        ],
        0,
    ),
    (
        "GOVERNANCE",
        "Why are audit records important?",
        [
            "They provide accountability and traceability",
            "They replace customer consent",
            "They eliminate review",
            "They advertise products",
        ],
        0,
    ),
    (
        "GOVERNANCE",
        "What is the correct response to suspected fraud?",
        ["Follow the approved escalation process", "Delete the record", "Ignore it", "Confront publicly"],
        0,
    ),
    (
        "GOVERNANCE",
        "What should sales communication avoid?",
        ["Misleading guarantees and hidden limitations", "Clear explanations", "Documented consent", "Needs analysis"],
        0,
    ),
    (
        "GOVERNANCE",
        "Why is explicit consent recorded?",
        [
            "To evidence an informed authorized action",
            "To bypass verification",
            "To guarantee acceptance",
            "To remove policy terms",
        ],
        0,
    ),
    (
        "GOVERNANCE",
        "What is the safest action when identity documents conflict?",
        [
            "Pause and send for correction or review",
            "Select one at random",
            "Alter the documents",
            "Ignore the conflict",
        ],
        0,
    ),
    (
        "GOVERNANCE",
        "What is the purpose of needs analysis?",
        [
            "Match recommendations to relevant customer circumstances",
            "Sell the highest premium only",
            "Avoid documentation",
            "Guarantee returns",
        ],
        0,
    ),
]


def question_bank() -> dict[str, dict]:
    result = {}
    for index, (category, prompt, options, answer) in enumerate(_BASE, start=1):
        result[f"Q{index:02}"] = {"category": category, "prompt": prompt, "options": options, "answer": answer}
        result[f"Q{index + 25:02}"] = {
            "category": category,
            "prompt": f"Scenario check: {prompt}",
            "options": options,
            "answer": answer,
        }
    return result


QUESTIONS = question_bank()


def randomized_order(seed: str) -> list[str]:
    ids = list(QUESTIONS)
    random.Random(seed).shuffle(ids)  # noqa: S311 - deterministic per-attempt ordering, not a security token
    return ids


def public_question(question_id: str) -> dict:
    item = QUESTIONS[question_id]
    return {"id": question_id, "category": item["category"], "prompt": item["prompt"], "options": item["options"]}


def certificate_seal(certificate_number: str, application_id: str, issued_at: str, secret: str) -> str:
    return hashlib.sha256(f"{certificate_number}|{application_id}|{issued_at}|{secret}".encode()).hexdigest()
