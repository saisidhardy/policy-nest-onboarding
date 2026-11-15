"""RAG Knowledge Base & Applicant Recovery Assistant Service.

Grounded directly in:
1. POSP ONBOARDING: Applicant Recovery & Agent Action Manual (7 Pages)
2. POSP QUICK-START HANDBOOK: Before You Start Onboarding (2 Pages)
3. IRDAI POSP Guidelines 2016 & InsuranceDekho PS-01 Rules
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import time
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.application import REQUIRED_DOC_TYPES, Application, ApplicationDocument
from app.models.base import utcnow
from app.models.rules import ApplicationAppeal, ApplicationDecision
from app.models.training import TrainingRecord
from app.models.user import User
from app.models.verification import DocumentExtraction, VerificationCheck
from app.schemas.rag import (
    ApplicantBlockerItem,
    ApplicantLiveState,
    RAGChatResponse,
    RAGChunkOut,
)
from app.services import analytics as analytics_service


@dataclass
class RAGChunk:
    id: str
    source: str
    section: str
    stage: str
    title: str
    text: str
    citations: list[str]
    actionable_steps: list[str]
    sample_script: str | None
    is_escalation_indicator: bool
    keywords: list[str]


# Authoritative Knowledge Base compiled from the official manuals
MANUAL_CHUNKS: list[RAGChunk] = [
    # --- Recovery Manual: Section 1 (Initial Onboarding Abandonment) ---
    RAGChunk(
        id="recovery_sec1_never_uploaded",
        source="POSP Recovery & Agent Action Manual",
        section="1. Never Uploaded Documents (Initial Abandonment)",
        stage="DOCUMENT_UPLOAD",
        title="Handling Never Uploaded Documents & 7-Day Expiry",
        text=(
            "What Happened: The applicant started registration but never uploaded documents. "
            "Important: Some applications expire after 7 days if documents are not submitted.\n"
            "Action Steps:\n"
            "1. Call or message the applicant.\n"
            "2. Ask if they need help understanding document requirements.\n"
            "3. Explain that documents can be uploaded ONE AT A TIME — you do NOT need to upload everything together.\n"
            "4. Help them complete the first upload.\n"
            "5. Follow up until all 6 required documents are submitted.\n"
            "Six Documents to Collect:\n"
            "1. PAN Card\n"
            "2. Aadhaar Front\n"
            "3. Aadhaar Back\n"
            "4. Class 10 Marksheet\n"
            "5. Cancelled Cheque / Bank Statement\n"
            "6. Live Selfie\n"
            "Agent Reminder: Never assume the applicant is unwilling. They may simply need assistance."
        ),
        citations=["Recovery Manual Page 2 §1", "Quick-Start Handbook Step 4"],
        actionable_steps=[
            "Upload documents one at a time at your own pace",
            "Keep originals handy in bright daylight",
            "Complete within 7 days to prevent application expiry",
        ],
        sample_script=(
            "Hello! You have started your POSP registration but your document upload is still pending. "
            "I can help you complete it step by step. You don't need to upload everything together."
        ),
        is_escalation_indicator=False,
        keywords=["upload", "never uploaded", "pending", "documents", "7 days", "expire", "expiry", "abandon", "six documents"],
    ),

    # --- Recovery Manual: Section 2 (Rejected on Eligibility & Non-Auto-Reject Rules) ---
    RAGChunk(
        id="recovery_sec2_eligibility_checks",
        source="POSP Recovery & Agent Action Manual",
        section="2. Rejected on Eligibility (Eligibility Review)",
        stage="VERIFICATION",
        title="Statutory Eligibility Verification & Pre-Closing Checklist",
        text=(
            "Before closing or confirming a rejection on an application, verify:\n"
            "• Age: Applicant was at least 18 years old on application date.\n"
            "• Education: Class 10 PASS from a recognised board (State Board, CBSE, ICSE, NIOS).\n"
            "• PAN: Valid individual PAN (4th character is 'P').\n"
            "• Exclusivity: Existing POSP registration with another insurer confirmed.\n"
            "• Name: Legitimate name variations considered.\n"
            "• DOB: Compare PAN, Aadhaar and marksheet.\n"
            "• Bank: Applicant's own account (or first holder in joint account)."
        ),
        citations=["Recovery Manual Page 3 §2", "IRDAI Guidelines 2016 §3"],
        actionable_steps=[
            "Verify age >= 18 on application date",
            "Confirm Class 10 pass status from recognised board",
            "Validate individual PAN character 'P'",
        ],
        sample_script="Let me cross-verify your eligibility credentials against statutory IRDAI guidelines.",
        is_escalation_indicator=False,
        keywords=["eligibility", "age", "18", "education", "class 10", "pan", "individual", "exclusivity", "dob", "bank account"],
    ),

    RAGChunk(
        id="recovery_sec2_dont_reject_automatically",
        source="POSP Recovery & Agent Action Manual",
        section="2. Rejected on Eligibility (Non-Auto-Reject Safeguards)",
        stage="VERIFICATION",
        title="Golden Guardrail: DON'T Reject These Cases Automatically",
        text=(
            "DO NOT REJECT THESE CASES AUTOMATICALLY:\n"
            "• Initials instead of full names (e.g., 'R. Sharma' vs 'Rajiv Sharma')\n"
            "• Missing or additional middle names (e.g., 'Rajiv Kumar Sharma' vs 'Rajiv Sharma')\n"
            "• Reversed name order (e.g., 'Sharma Rajiv' vs 'Rajiv Sharma')\n"
            "• Common spelling variations (e.g., 'Vikas' vs 'Bikash', 'Asha' vs 'Aasa')\n"
            "• Aadhaar showing only year of birth (DOB comparison must accept YYYY match)\n"
            "• Joint bank account where applicant is FIRST HOLDER\n"
            "• Recognised NIOS (National Institute of Open Schooling) or state board marksheet\n"
            "• Unavailable registry or third-party verification service\n\n"
            "ACTION INDICATORS:\n"
            "• GREEN — Clear eligibility failure: Record the exact statutory reason.\n"
            "• AMBER — Uncertain identity or document: Request clarification.\n"
            "• BLUE — Human-only decision: Escalate to reviewer / raise formal appeal.\n\n"
            "CRITICAL MANDATE: A spelling difference is not automatically proof of a different person. "
            "Never override a human-review requirement."
        ),
        citations=["Recovery Manual Page 3 §2", "PS-01 Rulebook §5.1 (8-Tier Name Matching)"],
        actionable_steps=[
            "Do not abandon application due to initials or missing middle names",
            "Joint accounts are valid if candidate is 1st account holder",
            "NIOS and State Board matriculation certificates are fully valid",
            "If wrongly rejected or uncertain, raise a formal appeal for human reviewer review",
        ],
        sample_script=(
            "Under POSP Onboarding Guidelines, spelling variations, initials, and NIOS marksheets "
            "cannot be automatically rejected. We can submit this for human reviewer clearance."
        ),
        is_escalation_indicator=True,
        keywords=[
            "reject", "name", "spelling", "initials", "middle name", "reversed", "nios", "joint", "joint account",
            "first holder", "year of birth", "yob", "blue", "human", "appeal", "escalate", "wrong rejection",
        ],
    ),

    # --- Recovery Manual: Section 3 (No Reply to Correction Request) ---
    RAGChunk(
        id="recovery_sec3_correction_recovery",
        source="POSP Recovery & Agent Action Manual",
        section="3. No Reply to Correction Request",
        stage="VERIFICATION",
        title="4 Recovery Steps for Pending Document Corrections",
        text=(
            "What Happened: The applicant was asked to correct a document but did not respond.\n"
            "Your 4 Recovery Steps:\n"
            "1. UNDERSTAND: Did the applicant receive the message? Did they understand what was wrong? "
            "Are they facing difficulty uploading again?\n"
            "2. EXPLAIN: Show the exact document and issue.\n"
            "3. HELP: Guide them through the correction and re-upload.\n"
            "4. CONFIRM: Check whether the new document has been received and processed.\n\n"
            "COMMON CORRECTIONS & SIMPLE INSTRUCTIONS:\n"
            "• Blurry image -> Take a clear photo in daylight.\n"
            "• Cropped document -> Show all four corners.\n"
            "• Glare -> Avoid reflections; turn flash OFF.\n"
            "• Name spelling -> Submit clarification or supporting gazette/aadhaar document.\n"
            "• Bank mismatch -> Upload proof of own bank account (cancelled cheque or statement with printed name).\n"
            "• Low selfie match -> Take a fresh live selfie in good daylight without glasses or cap.\n\n"
            "AGENT REMINDER: Ask for all outstanding corrections together in one pass, not one at a time."
        ),
        citations=["Recovery Manual Page 4 §3", "Quick-Start Handbook Step 3"],
        actionable_steps=[
            "Identify the specific deficient document slot",
            "Retake photo in bright natural daylight with flash turned OFF",
            "Ensure all 4 corners of the document are visible",
            "Make sure account holder name is printed clearly on cheque or statement",
        ],
        sample_script=(
            "Your application is not complete yet. One or more documents need a small correction. "
            "I can explain exactly what needs to be changed and help you upload it again."
        ),
        is_escalation_indicator=False,
        keywords=[
            "correction", "rework", "blurry", "blur", "glare", "cropped", "corners", "bank mismatch",
            "selfie match", "re-upload", "fix", "reflection", "flash",
        ],
    ),

    # --- Recovery Manual: Section 4 (Verified, Training Not Started) ---
    RAGChunk(
        id="recovery_sec4_training_not_started",
        source="POSP Recovery & Agent Action Manual",
        section="4. Verified, Training Not Started",
        stage="TRAINING",
        title="Converting KYC Verification into Action (15-Hour POSP Training)",
        text=(
            "What Happened: KYC was completed, but the applicant did not start the 15-hour POSP training.\n"
            "Your Job: Convert Verification into Action:\n"
            "1. Congratulate the applicant on completing KYC.\n"
            "2. Explain the next step: 15 hours of mandatory online POSP training.\n"
            "3. Share official training access instructions.\n"
            "4. Explain how to resume or continue training anytime on web or mobile.\n"
            "5. Follow up on training progress.\n"
            "6. Explain the online examination and next steps.\n\n"
            "Simple Progress Tracker:\n"
            "■ KYC verified (Done)\n"
            "■ Training started\n"
            "■ Training completed (15 hours)\n"
            "■ POSP examination passed\n"
            "■ Certificate issued"
        ),
        citations=["Recovery Manual Page 5 §4", "IRDAI Training Syllabus 2016"],
        actionable_steps=[
            "Log in to the LMS module using your PolicyNest credentials",
            "Complete 15 hours of self-paced training across Life and General Insurance modules",
            "Attempt the practice quiz and take the final online POSP exam",
        ],
        sample_script=(
            "Congratulations! Your document verification is complete. Your next step is to complete the 15-hour POSP training. "
            "Let me help you get started."
        ),
        is_escalation_indicator=False,
        keywords=["training", "lms", "15 hours", "modules", "exam", "examination", "kyc approved", "verified", "start training"],
    ),

    # --- Recovery Manual: Section 5 & 6 (In Progress & Certified Agents) ---
    RAGChunk(
        id="recovery_sec5_in_progress",
        source="POSP Recovery & Agent Action Manual",
        section="5. Still In Progress & 6. Certified Agents",
        stage="IN_PROGRESS",
        title="In-Progress Escalations and Certified Agent Support",
        text=(
            "Still in Progress Guidelines:\n"
            "• Remember: NEVER assume an application is abandoned simply because it is in progress.\n"
            "• Open the application, identify last completed step, and find pending requirements.\n"
            "• Escalate if the application is waiting on internal processing (e.g. queue delay).\n\n"
            "Certified Agents Support:\n"
            "• Congratulate candidate on becoming a certified POSP.\n"
            "• Confirm that they have received their official certificate with QR code and cryptographic seal.\n"
            "• Explain next steps for starting their POSP business and direct them to sales support."
        ),
        citations=["Recovery Manual Page 6 §5-6"],
        actionable_steps=[
            "Check current queue wait time",
            "Download tamper-evident certificate from your dashboard",
            "Verify certificate anytime at /verify-certificate",
        ],
        sample_script="Congratulations on becoming a certified POSP! Your onboarding is complete. We are here to help you take your next step.",
        is_escalation_indicator=False,
        keywords=["in progress", "certified", "certificate", "passed", "sales support", "internal processing"],
    ),

    # --- Recovery Manual: Section 7 (Golden Rules) ---
    RAGChunk(
        id="recovery_sec7_golden_rules",
        source="POSP Recovery & Agent Action Manual",
        section="7. Golden Rules for Every Onboarding Agent",
        stage="GENERAL",
        title="The Golden DOs and DON'Ts of POSP Onboarding",
        text=(
            "DO ✓:\n"
            "• Use simple language\n"
            "• Explain one step at a time\n"
            "• Show exactly what is missing\n"
            "• Ask for all corrections together\n"
            "• Escalate uncertain cases (BLUE indicator)\n"
            "• Confirm every successful step\n"
            "• Be patient and supportive\n\n"
            "DON'T ✕:\n"
            "• Use complicated technical terms\n"
            "• Overwhelm applicants\n"
            "• Send vague correction requests\n"
            "• Ask for one correction per message (ping-pong)\n"
            "• Reject without sufficient evidence\n"
            "• Assume an upload means verification\n"
            "• Blame applicants for mistakes\n\n"
            "MISSION: Don't just process applications. Help people become certified POSPs. "
            "Every applicant deserves a clear explanation, a fair decision, and a simple next step."
        ),
        citations=["Recovery Manual Page 7 §7"],
        actionable_steps=[
            "Follow single-pass correction policy",
            "Escalate ambiguous cases to human supervisor instead of rejecting",
        ],
        sample_script="Every applicant deserves a clear explanation, a fair decision and a simple next step.",
        is_escalation_indicator=False,
        keywords=["golden rules", "dos and donts", "mission", "priorities", "help", "support", "fair decision"],
    ),

    # --- Quick-Start Handbook: Step 1 (Basic Eligibility) ---
    RAGChunk(
        id="quickstart_step1_eligibility",
        source="POSP Quick-Start Handbook",
        section="Step 1: Confirm Basic Eligibility",
        stage="DOCUMENT_UPLOAD",
        title="5 Mandatory Pre-Onboarding Eligibility Criteria",
        text=(
            "Check these 5 criteria first for fast, zero-rejection approval:\n"
            "1. Age: 18+ years on the date of application.\n"
            "2. Education: Class 10 PASS from a recognised board (State Board / CBSE / ICSE / NIOS).\n"
            "3. PAN Card: Valid Individual PAN in your own name.\n"
            "4. Exclusivity: No existing POSP registration with another insurer or broker.\n"
            "5. Bank Account: Account in your own name (or first holder in a joint account).\n\n"
            "Cross-Check Before Uploading: Your Name and Date of Birth must match across PAN, Aadhaar, Class 10 Marksheet, and Bank Proof."
        ),
        citations=["Quick-Start Handbook Page 1 Step 1"],
        actionable_steps=[
            "Ensure you are at least 18 years of age",
            "Have your original Class 10 pass certificate ready",
            "Verify your PAN has 4th letter 'P'",
        ],
        sample_script="Before uploading, confirm you are 18+, have passed Class 10, have an individual PAN, and own bank account.",
        is_escalation_indicator=False,
        keywords=["quick start", "handbook", "eligibility", "criteria", "rules", "prerequisites", "step 1"],
    ),

    # --- Quick-Start Handbook: Step 2 & 3 (Photo & Upload Rules) ---
    RAGChunk(
        id="quickstart_step3_photo_upload_rules",
        source="POSP Quick-Start Handbook",
        section="Step 3: Follow Photo & Upload Rules",
        stage="DOCUMENT_UPLOAD",
        title="Photo & Camera Upload Guidelines: Do's and Don'ts",
        text=(
            "DO THIS ✓ vs DON'T DO THIS ✕:\n"
            "• Lighting: ✓ Capture in bright daylight | ✕ Blurry, dark, or shaky photos\n"
            "• Corners: ✓ Show all 4 document corners | ✕ Cropped edges or fingers covering text\n"
            "• Flash / Glare: ✓ Turn flash OFF; tilt away from light | ✕ White glare hiding photo or ID number\n"
            "• Live Selfie: ✓ Plain background, clear face, no glasses | ✕ Backlit face, cap/mask, or photo of a photo\n"
            "• Phone Setup: ✓ Allow camera access & stable internet | ✕ Blocked camera permission or oversized files\n\n"
            "Final Check Before Clicking Start:\n"
            "Originals in hand • Camera permission ON • Name & DOB verified • SMS/Email alerts active."
        ),
        citations=["Quick-Start Handbook Page 2 Step 3"],
        actionable_steps=[
            "Turn camera flash OFF to prevent white glare over text",
            "Place document on a flat, contrasting surface",
            "Ensure all 4 borders and corners are visible in frame",
            "Remove spectacles, cap, or mask before taking the live selfie",
        ],
        sample_script="Turn flash off, take photo in daylight showing all 4 corners, and ensure name and numbers are sharp and legible.",
        is_escalation_indicator=False,
        keywords=[
            "photo", "camera", "lighting", "glare", "flash", "corners", "selfie", "dark", "blurry",
            "upload rules", "crop", "permission",
        ],
    ),

    # --- Quick-Start Handbook: Step 4 (5-Stage Path to Certification) ---
    RAGChunk(
        id="quickstart_step4_path_to_certification",
        source="POSP Quick-Start Handbook",
        section="Step 4: Your 5-Stage Path to Certification",
        stage="GENERAL",
        title="The 5-Stage Roadmap from Intake to IRDAI POSP License",
        text=(
            "Stage 01: Document Upload — Upload all 6 clear documents (complete within 7 days so your form doesn't expire).\n"
            "Stage 02: KYC Verification — Watch SMS/WhatsApp/Email; reply fast if any correction is requested.\n"
            "Stage 03: 15-Hour Training — Log in with your official credentials and finish all 15 training hours.\n"
            "Stage 04: POSP Exam — Complete and pass the online POSP certification exam.\n"
            "Stage 05: POSP Certificate — Download your certificate — your onboarding is complete!"
        ),
        citations=["Quick-Start Handbook Page 2 Step 4"],
        actionable_steps=[
            "Stage 1: Complete 6 document slots within 7 days",
            "Stage 2: Receive instant automated verification and reviewer review",
            "Stage 3: Complete 15 hours of interactive LMS training",
            "Stage 4: Pass the online IRDAI IC-38 exam",
            "Stage 5: Mint your official POSP accreditation license",
        ],
        sample_script="Your path consists of 5 clear stages: Document Upload -> KYC Verification -> 15-Hour Training -> Exam -> Certificate.",
        is_escalation_indicator=False,
        keywords=["stages", "5 stages", "roadmap", "certification", "path", "overview", "process"],
    ),

    # --- Company Policy & Problem Statement Alignment (PS-01) ---
    RAGChunk(
        id="policy_ps01_name_matching_8tier",
        source="Company Policy (PS-01)",
        section="Deterministic Rules & 8-Tier Indian Name Matcher",
        stage="VERIFICATION",
        title="8-Tier Indian Name Resolution & False Rejection Elimination",
        text=(
            "PolicyNest enforces an 8-Tier Indian Name Matching Engine to handle authentic linguistic diversity:\n"
            "• Tier 1: Exact case-insensitive match (100% score).\n"
            "• Tier 2: Token-set reordering (e.g. 'Verma Asha' vs 'Asha Verma' -> 98% score).\n"
            "• Tier 3: Subsequence token match (e.g. 'Mohd' vs 'Mohammed').\n"
            "• Tier 4: Initials expansion (e.g. 'A. R. Verma' vs 'Asha Ramesh Verma' -> 88% score).\n"
            "• Tier 5: Jaro-Winkler phonetic similarity with 0.85 threshold.\n"
            "• Tier 6: Matrimonial surname modification (flags for human verification with marriage proof).\n"
            "• Tier 7: Joint account first-holder matching.\n"
            "• Tier 8: Strict Non-Auto-Reject Guardrail — no candidate can be auto-rejected for name variation without human review.\n\n"
            "Turnaround Time (TAT) Target: Authoritative operational SLA is 5.7 days maximum (down from 8.4-day manual baseline)."
        ),
        citations=["PS-01 Architecture Standard §5.1", "Recovery Manual Page 3 §2"],
        actionable_steps=[
            "Name variations are automatically scored across all 8 tiers",
            "Initials and rearranged names are never auto-rejected",
            "If an adverse rejection occurred, applicant can submit formal appeal",
        ],
        sample_script="Our 8-tier name matching engine recognizes Indian name formats, initials, and order reversals without auto-rejection.",
        is_escalation_indicator=True,
        keywords=["8-tier", "name matcher", "initials", "surname", "jaro winkler", "phonetic", "tat", "5.7 days"],
    ),
]


def retrieve_relevant_chunks(query: str, current_stage: str | None = None) -> list[RAGChunk]:
    """Retrieve ranked manual chunks using hybrid keyword overlap and stage proximity."""
    tokens = set(re.findall(r"\w+", query.lower()))
    scored_chunks: list[tuple[float, RAGChunk]] = []

    for chunk in MANUAL_CHUNKS:
        score = 0.0

        # Keyword match
        for kw in chunk.keywords:
            if kw.lower() in query.lower():
                score += 3.0
            kw_tokens = set(re.findall(r"\w+", kw.lower()))
            overlap = len(tokens.intersection(kw_tokens))
            score += overlap * 1.5

        # Content text match
        text_tokens = set(re.findall(r"\w+", chunk.text.lower()))
        text_overlap = len(tokens.intersection(text_tokens))
        score += min(text_overlap * 0.1, 5.0)

        # Stage relevance bonus
        if current_stage and chunk.stage == current_stage:
            score += 2.0

        # Escalation bonus if query contains "appeal", "reject", "wrong", "human"
        if chunk.is_escalation_indicator and any(w in query.lower() for w in ["appeal", "reject", "rejection", "human", "supervisor", "wrong"]):
            score += 4.0

        scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    # Return top 3 chunks with positive score, or fallback to default top 2
    positive = [c for s, c in scored_chunks if s > 0]
    return positive[:3] if positive else [c for _, c in scored_chunks[:2]]


def inspect_applicant_live_state(
    db: Session,
    user: User | None,
    application_id: uuid.UUID | None = None,
) -> ApplicantLiveState:
    """Inspect the database to build a complete real-time applicant state analysis."""
    if user is None and application_id is None:
        return ApplicantLiveState(
            has_application=False,
            priority_group="FRESH",
            priority_group_label="Prospective Candidate",
            current_stage="DOCUMENT_UPLOAD",
            documents_completed_count=0,
            missing_documents=list(REQUIRED_DOC_TYPES),
        )

    # Find the target application
    app: Application | None = None
    if application_id:
        app = db.scalar(select(Application).where(Application.id == application_id))
    elif user:
        app = db.scalar(
            select(Application)
            .where(Application.user_id == user.id)
            .order_by(desc(Application.created_at))
        )

    if app is None:
        return ApplicantLiveState(
            has_application=False,
            priority_group="FRESH",
            priority_group_label="Prospective Candidate",
            current_stage="DOCUMENT_UPLOAD",
            documents_completed_count=0,
            missing_documents=list(REQUIRED_DOC_TYPES),
        )

    # Query uploaded documents
    uploaded_docs = list(
        db.scalars(
            select(ApplicationDocument).where(
                ApplicationDocument.application_id == app.id,
                ApplicationDocument.is_current.is_(True),
            )
        )
    )
    uploaded_types = {d.doc_type for d in uploaded_docs}
    missing = [dt for dt in REQUIRED_DOC_TYPES if dt not in uploaded_types]

    # Query checks & decisions
    checks = list(
        db.scalars(
            select(VerificationCheck).where(VerificationCheck.application_id == app.id)
        )
    )
    failed_checks = [c for c in checks if c.status in ("FAILED", "NEEDS_INFO")]

    # Query open appeals
    open_appeal = db.scalar(
        select(ApplicationAppeal).where(
            ApplicationAppeal.application_id == app.id,
            ApplicationAppeal.status == "OPEN",
        )
    )

    # Query training progress
    training_rec = db.scalar(
        select(TrainingRecord).where(TrainingRecord.application_id == app.id)
    )
    training_hours = float(training_rec.completed_hours) if training_rec else 0.0

    # Calculate days since creation & expiry
    days_since = (utcnow() - app.created_at).days
    days_remaining = max(0, 7 - days_since)

    # Derive Blockers & Priority Group
    blockers: list[ApplicantBlockerItem] = []

    # 1. Check Missing Documents
    if missing and app.status in ("DRAFT", "NEEDS_MORE_INFO"):
        blockers.append(
            ApplicantBlockerItem(
                blocker_code="MISSING_DOCUMENTS",
                title=f"{len(missing)} Mandatory Documents Pending",
                description=f"Missing: {', '.join(missing).replace('_', ' ')}. Documents can be uploaded one at a time.",
                severity="BLOCKING",
                suggested_action="Upload pending documents individually. Bright daylight, flash OFF, all 4 corners visible.",
                manual_citation="POSP Recovery Manual §1 & Quick-Start Step 3",
                can_appeal=False,
            )
        )

    # 2. Check Document Quality
    extractions = list(
        db.scalars(
            select(DocumentExtraction).where(DocumentExtraction.application_id == app.id)
        )
    )
    for ext in extractions:
        if ext.quality_status in ("FAIL", "WARN"):
            doc_type = ext.predicted_doc_type or "DOCUMENT"
            issues: list[str] = []
            if ext.blur_score and ext.blur_score > 0.4:
                issues.append("Photo is blurry")
            if ext.glare_ratio and ext.glare_ratio > 0.05:
                issues.append("Reflection/glare on text")
            if ext.edge_clip_ratio and ext.edge_clip_ratio > 0.05:
                issues.append("Document corners cut off")
            desc_text = ", ".join(issues) if issues else "Image clarity below statutory threshold."
            blockers.append(
                ApplicantBlockerItem(
                    blocker_code=f"QUALITY_{doc_type}",
                    title=f"Clarity Issue on {doc_type.replace('_', ' ')}",
                    description=f"{desc_text}. Per Manual Rule 3: Take daylight photo with flash OFF.",
                    severity="WARNING",
                    suggested_action="Re-upload in natural light showing all 4 corners.",
                    manual_citation="POSP Recovery Manual §3: Common Corrections",
                    can_appeal=False,
                )
            )

    # 3. Check Failed Verification Checks
    for fc in failed_checks:
        is_name_check = "name" in fc.check_code.lower()
        is_nios_or_edu = "edu" in fc.check_code.lower() or "matric" in fc.check_code.lower()
        is_bank = "bank" in fc.check_code.lower() or "cheque" in fc.check_code.lower()

        # Check if this qualifies for Human Escalation / Appeal under Manual Rule 2 (BLUE)
        can_appeal_this = is_name_check or is_nios_or_edu or is_bank or app.status == "REJECTED"

        blockers.append(
            ApplicantBlockerItem(
                blocker_code=fc.check_code,
                title=f"Verification Check Flagged: {fc.check_name}",
                description=fc.failure_reason or "Discrepancy detected during deterministic check.",
                severity="BLOCKING" if app.status == "REJECTED" else "WARNING",
                suggested_action=(
                    "Under Manual §2, spelling variations, joint bank accounts, and NIOS marksheets cannot be auto-rejected. "
                    "You may request a human reviewer exception or appeal."
                    if can_appeal_this
                    else "Submit corrected document."
                ),
                manual_citation="POSP Recovery Manual §2: Non-Auto-Reject Rules (BLUE Indicator)",
                can_appeal=can_appeal_this,
            )
        )

    # Classify Priority Group per Manual
    if app.status == "REJECTED":
        priority_group = "REJECTED_ELIGIBILITY"
        priority_group_label = "2. Rejected on Eligibility (Review & Appeal Eligible)"
        current_stage = "VERIFICATION"
    elif app.status == "NEEDS_MORE_INFO":
        priority_group = "NO_REPLY_CORRECTION"
        priority_group_label = "3. Correction Requested (Action Required)"
        current_stage = "VERIFICATION"
    elif app.status in ("KYC_APPROVED", "TRAINING_IN_PROGRESS"):
        priority_group = "VERIFIED_TRAINING_PENDING"
        priority_group_label = "4. Verified, Training in Progress"
        current_stage = "TRAINING"
    elif app.status == "CERTIFIED":
        priority_group = "CERTIFIED"
        priority_group_label = "6. Certified POSP Agent"
        current_stage = "CERTIFICATION"
    elif len(uploaded_docs) == 0:
        priority_group = "NEVER_UPLOADED_DOCS"
        priority_group_label = "1. Never Uploaded Documents (Initial Intake)"
        current_stage = "DOCUMENT_UPLOAD"
    else:
        priority_group = "IN_PROGRESS"
        priority_group_label = "5. Application In Progress"
        current_stage = "DOCUMENT_UPLOAD" if len(uploaded_docs) < 6 else "VERIFICATION"

    return ApplicantLiveState(
        has_application=True,
        application_id=str(app.id),
        reference_code=app.reference_code,
        status=app.status,
        priority_group=priority_group,
        priority_group_label=priority_group_label,
        current_stage=current_stage,
        documents_completed_count=len(uploaded_docs),
        documents_total_count=6,
        missing_documents=missing,
        active_blockers=blockers,
        has_open_appeal=open_appeal is not None,
        training_hours_completed=round(training_hours, 1),
        training_hours_required=15.0,
        days_since_created=days_since,
        days_remaining_before_expiry=days_remaining,
    )


def generate_rag_chat_response(
    db: Session,
    query: str,
    user: User | None = None,
    application_id: uuid.UUID | None = None,
    language: str = "EN",
) -> RAGChatResponse:
    """Blend RAG retrieval with real-time applicant state monitoring and appeal escalation."""
    start_time = time.perf_counter()

    # 1. Real-time applicant state inspection
    live_state = inspect_applicant_live_state(db, user, application_id)

    # 2. Retrieve relevant manual chunks
    chunks = retrieve_relevant_chunks(query, current_stage=live_state.current_stage)

    # 3. Determine if candidate should be offered an appeal
    # If the application is REJECTED, or if there is an unresolvable blocker flagged with can_appeal,
    # or if the query explicitly asks to appeal/escalate
    query_lower = query.lower()
    asks_for_appeal = any(w in query_lower for w in ["appeal", "escalate", "human", "supervisor", "rejected", "wrong rejection"])
    has_appealable_blocker = any(b.can_appeal for b in live_state.active_blockers)
    is_rejected = live_state.status == "REJECTED"

    can_appeal = (is_rejected or has_appealable_blocker or asks_for_appeal) and not live_state.has_open_appeal and live_state.has_application

    appeal_prefill_reason = None
    appeal_guidance = None
    if can_appeal:
        reasons = [b.title for b in live_state.active_blockers if b.can_appeal]
        blocker_summary = "; ".join(reasons) if reasons else "Requesting Senior Reviewer exception for name/credential variation."
        appeal_prefill_reason = f"Formal Appeal for {live_state.reference_code}: Under Manual §2 non-auto-reject rules, requesting human review for {blocker_summary}"
        appeal_guidance = (
            "Per POSP Recovery Manual Section 2 (BLUE Indicator): Legitimate name variations, initials, "
            "joint accounts (1st holder), and NIOS marksheets require a Human Reviewer decision and must not be rejected. "
            "Click 'Raise Formal Appeal' below to route your file directly to a Senior Reviewer."
        )

    # 4. Formulate contextual, grounded answer
    answer_parts: list[str] = []

    # Greeting & State awareness
    if live_state.has_application:
        status_readable = (live_state.status or "DRAFT").replace("_", " ")
        answer_parts.append(
            f"**Application Reference:** `{live_state.reference_code}` (Status: **{status_readable}** · Stage: **{live_state.current_stage}**).\n"
        )
        if live_state.active_blockers:
            top_blocker = live_state.active_blockers[0]
            answer_parts.append(f"⚠️ **Current Active Blocker:** {top_blocker.title} — {top_blocker.description}\n")

    # Synthesize guidance from retrieved manual chunks
    for i, chunk in enumerate(chunks, 1):
        answer_parts.append(f"### 📖 {chunk.section}")
        answer_parts.append(chunk.text)
        if chunk.actionable_steps:
            answer_parts.append("\n**Action Steps from Manual:**")
            for step in chunk.actionable_steps:
                answer_parts.append(f"• {step}")
        answer_parts.append("")

    # Add Blocker-specific resolution
    if can_appeal:
        answer_parts.append("---")
        answer_parts.append(
            "### 🛡️ Human Reviewer Appeal Option\n"
            "If your document cannot be automatically verified due to legitimate variations (e.g., initials, marriage surname change, "
            "or NIOS board marksheet), **you have the statutory right to raise a formal appeal**.\n"
            "This will immediately transfer your application to a Senior Reviewer for priority resolution."
        )

    answer = "\n\n".join(answer_parts)

    # Voice Script generation (concise summary for audio TTS)
    voice_script: str
    if language == "HI":
        voice_script = (
            f"नमस्ते! आपके आवेदन {live_state.reference_code or ''} की वर्तमान स्थिति {live_state.current_stage} है। "
            f"दस्तावेज़ साफ़ दिन की रोशनी में फ़्लैश बंद करके अपलोड करें। "
            + ("यदि कोई समस्या है तो आप वरिष्ठ समीक्षक को अपील कर सकते हैं।" if can_appeal else "हम आपकी पूरी सहायता करेंगे।")
        )
    else:
        voice_script = (
            f"Hello! For your application {live_state.reference_code or 'at PolicyNest'}, you are at the {live_state.current_stage} stage. "
            f"Please ensure photos are taken in bright daylight with flash turned off, showing all four corners. "
            + ("You can also raise an appeal directly to a human reviewer if needed." if can_appeal else "We are here to help you get certified.")
        )

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # 5. Record telemetry & observability
    citations = list({cit for chunk in chunks for cit in chunk.citations})
    chunks_out = [
        RAGChunkOut(
            id=c.id,
            source=c.source,
            section=c.section,
            stage=c.stage,
            title=c.title,
            text=c.text,
            citations=c.citations,
            actionable_steps=c.actionable_steps,
            sample_script=c.sample_script,
            is_escalation_indicator=c.is_escalation_indicator,
        )
        for c in chunks
    ]

    # Ingest API Cost Record
    try:
        analytics_service.record_api_cost(
            db=db,
            provider="RAG_ASSISTANT",
            service_operation="recovery_manual_retrieval",
            application_id=uuid.UUID(live_state.application_id) if live_state.application_id else None,
            input_tokens=len(query.split()),
            output_tokens=len(answer.split()),
            latency_ms=latency_ms,
            success=True,
            environment="production",
        )
    except Exception:
        # Non-blocking observability capture
        pass

    return RAGChatResponse(
        query=query,
        answer=answer,
        language=language,
        citations=citations,
        relevant_chunks=chunks_out,
        applicant_state=live_state,
        can_appeal=can_appeal,
        appeal_prefill_reason=appeal_prefill_reason,
        appeal_guidance=appeal_guidance,
        voice_script=voice_script,
        latency_ms=round(latency_ms, 2),
    )
