"""PolicyNest Evaluation & Demo Scenario Seeder.

Generates representative POSP applications across all onboarding and verification stages:
1. STP Auto-Approved (Clean documents, 0 mismatch, automated approval)
2. Manual Review Desk & SLA Breach (>30 min wait, unassigned queue warning)
3. Rework Required (Bilingual checklist, cropped Class 10 marksheet)
4. Fraud Desk Escalation (Duplicate PAN flag & biometric mismatch alert)
5. LMS Certified POSP (15 hours completed, exam passed, IRDAI certificate issued)

Usage:
    python -m app.scripts.seed_demo_scenarios [--reset] [--json]
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import pathlib
import sys
from decimal import Decimal

# Ensure backend root is on sys.path when invoked directly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))

# Ensure fallback settings for standalone invocation
os.environ.setdefault("SECRET_KEY", "cutover-verification-ephemeral-key-min-32-chars")
os.environ.setdefault("DATABASE_URL", "sqlite:///./policynest_local.db")

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.core.db import get_sessionmaker
from app.core.security import hash_password
from app.models.application import Application
from app.models.base import utcnow
from app.models.rules import ApplicationAppeal, ApplicationDecision, RuleExecution
from app.models.training import TrainingRecord
from app.models.user import Role, User
from app.services.rules_engine import ensure_default_ruleset


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"

@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "TEXT"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_demo_scenarios")

DEMO_PASSWORD = "Demo@PolicyNest2026!"

DEMO_ACCOUNTS = [
    {
        "email": "posp_stp@policynest.demo",
        "name": "Rajesh Sharma",
        "role_code": "APPLICANT",
        "region": "NORTH",
    },
    {
        "email": "posp_review@policynest.demo",
        "name": "Sunita Devi",
        "role_code": "APPLICANT",
        "region": "NORTH",
    },
    {
        "email": "posp_rework@policynest.demo",
        "name": "Amit Kumar",
        "role_code": "APPLICANT",
        "region": "WEST",
    },
    {
        "email": "posp_fraud@policynest.demo",
        "name": "Vikram Singh",
        "role_code": "APPLICANT",
        "region": "SOUTH",
    },
    {
        "email": "posp_certified@policynest.demo",
        "name": "Priya Patel",
        "role_code": "APPLICANT",
        "region": "WEST",
    },
    {
        "email": "posp_regional@policynest.demo",
        "name": "Ananya Das",
        "role_code": "APPLICANT",
        "region": "EAST",
    },
    {
        "email": "posp_appeal@policynest.demo",
        "name": "Kavita Verma",
        "role_code": "APPLICANT",
        "region": "NORTH",
    },
    {
        "email": "posp_bank@policynest.demo",
        "name": "Mohammed Abdul Rahman Siddiqui",
        "role_code": "APPLICANT",
        "region": "SOUTH",
    },
    {
        "email": "posp_training@policynest.demo",
        "name": "Deepak Joshi",
        "role_code": "APPLICANT",
        "region": "NORTH",
    },
    {
        "email": "posp_age@policynest.demo",
        "name": "Aditya Varma",
        "role_code": "APPLICANT",
        "region": "SOUTH",
    },
    {
        "email": "reviewer@policynest.demo",
        "name": "Neha Verma (Review Officer)",
        "role_code": "SUPERVISOR",
        "region": "ALL",
    },
    {
        "email": "admin@policynest.demo",
        "name": "Arun Kapoor (Ops Lead)",
        "role_code": "ADMIN",
        "region": "ALL",
    },
]


def seed_demo_data(session: Session, reset: bool = False) -> dict:
    engine = session.get_bind()
    from sqlalchemy import inspect

    table_names = inspect(engine).get_table_names()
    if "users" not in table_names or "applications" not in table_names:
        logger.info("Initializing database schema from SQLAlchemy Base metadata...")
        import app.models  # noqa: F401
        from app.models.base import Base
        Base.metadata.create_all(engine)
        table_names = inspect(engine).get_table_names()
        if "users" not in table_names or "applications" not in table_names:
            raise RuntimeError("Database tables are not initialized. Run postgres_cutover or migrations first.")

    now = utcnow()
    created_users: dict[str, User] = {}

    # 1. Reset existing demo accounts if requested
    if reset:
        logger.info("Purging existing .demo accounts...")
        existing_demo_users = list(
            session.scalars(select(User).where(User.email.like("%@policynest.demo"))).all()
        )
        for u in existing_demo_users:
            session.delete(u)
        session.commit()

    # 2. Upsert / Fetch Demo Users
    roles_by_code = {r.code: r for r in session.scalars(select(Role)).all()}
    pwd_hash = hash_password(DEMO_PASSWORD)
    for acc in DEMO_ACCOUNTS:
        role_obj = roles_by_code.get(acc["role_code"])
        if not role_obj:
            role_obj = Role(
                code=acc["role_code"],
                name=acc["role_code"].title(),
                description=f"Demo {acc['role_code']} role",
                is_staff=acc["role_code"] != "APPLICANT",
            )
            session.add(role_obj)
            session.flush()
            roles_by_code[acc["role_code"]] = role_obj

        u = session.scalar(select(User).where(User.email == acc["email"]))
        if not u:
            u = User(
                email=acc["email"],
                full_name=acc["name"],
                password_hash=pwd_hash,
                role_id=role_obj.id,
                region=acc["region"],
                clearance_level=3 if acc["role_code"] in ("ADMIN", "SUPERVISOR") else 1,
                is_active=True,
                email_verified_at=now,
            )
            session.add(u)
            session.flush()
        created_users[acc["email"]] = u

    reviewer_user = created_users["reviewer@policynest.demo"]
    active_ruleset = ensure_default_ruleset(session)
    scenarios: list[dict] = []

    # 3. Create Demo Scenarios

    # --- Scenario 1: STP Auto-Approved ---
    user_stp = created_users["posp_stp@policynest.demo"]
    app_stp = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-STP-001"))
    if not app_stp:
        app_stp = Application(
            reference_code="PN-DEMO-STP-001",
            user_id=user_stp.id,
            status="KYC_APPROVED",
            current_step=6,
            region="NORTH",
            preferred_language="en",
            channel="DIRECT_PORTAL",
            full_name="Rajesh Sharma",
            date_of_birth=datetime.date(1992, 5, 14),
            gender="MALE",
            father_or_spouse_name="Ramesh Sharma",
            mobile="+919876543210",
            email="posp_stp@policynest.demo",
            pan_number="ABCPS1234F",
            aadhaar_last4="1234",
            address_line1="Plot 42, Civil Lines",
            city="Jaipur",
            state="Rajasthan",
            pincode="302006",
            same_as_permanent=True,
            education_level="GRADUATE",
            board_name="Rajasthan State Board",
            passing_year=2013,
            account_holder_name="Rajesh Sharma",
            bank_name="State Bank of India",
            ifsc_code="SBIN0001234",
            account_number_last4="5678",
            account_number_masked="••••••••5678",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(hours=2),
            submitted_at=now - datetime.timedelta(hours=2),
        )
        session.add(app_stp)
        session.flush()

        exec_stp = RuleExecution(
            application_id=app_stp.id,
            ruleset_id=active_ruleset.id,
            ruleset_version=active_ruleset.version,
            trigger_source="APPLICATION_SUBMIT",
            outcome="AUTO_APPROVE",
            recommended_status="APPROVED",
            eligibility_status="PASS",
            completeness_status="PASS",
            consistency_status="PASS",
            risk_level="LOW",
            auto_pass_eligible=True,
            requires_human_review=False,
            reason_codes=["ALL_CRITERIA_MET", "ZERO_MISMATCH", "PAN_BANK_VERIFIED"],
            rule_results=[],
            rework_items=[],
            risk_indicators=[],
            summary="Application cleared all deterministic policy checks with 0 mismatch and high OCR confidence.",
            executed_at=now - datetime.timedelta(hours=2),
        )
        session.add(exec_stp)

    scenarios.append(
        {
            "id": str(app_stp.id),
            "reference_code": "PN-DEMO-STP-001",
            "scenario": "STP Auto-Approved",
            "status": "KYC_APPROVED",
            "applicant": "Rajesh Sharma",
            "login": "posp_stp@policynest.demo",
            "highlight": "0 mismatch, high OCR quality, automatically cleared to LMS training.",
        }
    )

    # --- Scenario 2: Manual Review Desk & SLA Breach (>30m wait) ---
    user_rev = created_users["posp_review@policynest.demo"]
    app_rev = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-REV-002"))
    if not app_rev:
        app_rev = Application(
            reference_code="PN-DEMO-REV-002",
            user_id=user_rev.id,
            status="IN_REVIEW",
            current_step=6,
            region="NORTH",
            preferred_language="hi",
            channel="DIRECT_PORTAL",
            full_name="Sunita Devi",
            date_of_birth=datetime.date(1995, 8, 22),
            gender="FEMALE",
            father_or_spouse_name="Suresh Devi",
            mobile="+919811223344",
            email="posp_review@policynest.demo",
            pan_number="XYZPD5678K",
            aadhaar_last4="4567",
            address_line1="House 18, Sector 14",
            city="Lucknow",
            state="Uttar Pradesh",
            pincode="226016",
            same_as_permanent=True,
            education_level="HIGHER_SECONDARY",
            board_name="UP Board",
            passing_year=2015,
            account_holder_name="Sunita Devi",
            bank_name="Punjab National Bank",
            ifsc_code="PUNB0014500",
            account_number_last4="8901",
            account_number_masked="••••••••8901",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(minutes=48),
            submitted_at=now - datetime.timedelta(minutes=48),  # 48m > 30m SLA threshold
            assigned_reviewer_id=None,  # Unassigned, triggers SLA breach counter
        )
        session.add(app_rev)
        session.flush()

    scenarios.append(
        {
            "id": str(app_rev.id),
            "reference_code": "PN-DEMO-REV-002",
            "scenario": "Reviewer Queue (SLA Warning)",
            "status": "IN_REVIEW",
            "applicant": "Sunita Devi",
            "login": "posp_review@policynest.demo",
            "highlight": "Unassigned for 48 minutes (>30m SLA threshold). 8-digit Aadhaar masked.",
        }
    )

    # --- Scenario 3: Rework Required (Bilingual checklist) ---
    user_rew = created_users["posp_rework@policynest.demo"]
    app_rew = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-REW-003"))
    if not app_rew:
        app_rew = Application(
            reference_code="PN-DEMO-REW-003",
            user_id=user_rew.id,
            status="NEEDS_MORE_INFO",
            current_step=4,
            rework_count=1,
            region="WEST",
            preferred_language="hi",
            channel="DIRECT_PORTAL",
            full_name="Amit Kumar",
            date_of_birth=datetime.date(1990, 11, 3),
            gender="MALE",
            mobile="+919712345678",
            email="posp_rework@policynest.demo",
            pan_number="ABCPA9988M",
            aadhaar_last4="7890",
            address_line1="202 Shivam Heights",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380015",
            same_as_permanent=True,
            education_level="HIGHER_SECONDARY",
            passing_year=2008,
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(hours=5),
            submitted_at=now - datetime.timedelta(hours=5),
        )
        session.add(app_rew)
        session.flush()

        dec_rew = ApplicationDecision(
            application_id=app_rew.id,
            decided_by_user_id=reviewer_user.id,
            decided_by_role="REVIEWER",
            decision="NEEDS_MORE_INFO",
            previous_status="IN_REVIEW",
            new_status="NEEDS_MORE_INFO",
            is_override=False,
            reason_codes=["CLASS_10_MARKSHEET_BLURRED", "NAME_PARTIALLY_CROPPED"],
            reason_text=(
                "Class 10 mark sheet lower border is cropped and passing year is blurred. "
                "कृपया कक्षा 10 की अंकतालिका को स्पष्ट रूप से स्कैन करके पुनः अपलोड करें।"
            ),
            rework_items=[],
            created_at=now - datetime.timedelta(hours=3),
        )
        session.add(dec_rew)

    scenarios.append(
        {
            "id": str(app_rew.id),
            "reference_code": "PN-DEMO-REW-003",
            "scenario": "Rework Required",
            "status": "NEEDS_MORE_INFO",
            "applicant": "Amit Kumar",
            "login": "posp_rework@policynest.demo",
            "highlight": "Bilingual EN/HI correction checklist. Applicant can replace document directly in-place.",
        }
    )

    # --- Scenario 4: Fraud Desk Escalation ---
    user_fraud = created_users["posp_fraud@policynest.demo"]
    app_fraud = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-FRD-004"))
    if not app_fraud:
        app_fraud = Application(
            reference_code="PN-DEMO-FRD-004",
            user_id=user_fraud.id,
            status="IN_REVIEW",
            current_step=6,
            region="SOUTH",
            preferred_language="en",
            channel="DIRECT_PORTAL",
            full_name="Vikram Singh",
            date_of_birth=datetime.date(1988, 3, 10),
            gender="MALE",
            mobile="+919844001122",
            email="posp_fraud@policynest.demo",
            pan_number="XYZPV4433R",
            aadhaar_last4="3322",
            fraud_flag=True,
            fraud_reason="Biometric face mismatch (<38% confidence score) and duplicate PAN address flag.",
            fraud_escalated_at=now - datetime.timedelta(minutes=25),
            escalated_by_user_id=reviewer_user.id,
            escalated_at=now - datetime.timedelta(minutes=25),
            escalation_reason="Suspicious document metadata and duplicate identity fingerprint.",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(hours=1),
            submitted_at=now - datetime.timedelta(hours=1),
        )
        session.add(app_fraud)
        session.flush()

    scenarios.append(
        {
            "id": str(app_fraud.id),
            "reference_code": "PN-DEMO-FRD-004",
            "scenario": "Fraud Desk Investigation",
            "status": "IN_REVIEW (Fraud Flagged)",
            "applicant": "Vikram Singh",
            "login": "posp_fraud@policynest.demo",
            "highlight": "Appears in Fraud Desk tab. Requires Senior Reviewer clearance or confirmation reject.",
        }
    )

    # --- Scenario 5: LMS 15h Training & Certified POSP ---
    user_cert = created_users["posp_certified@policynest.demo"]
    app_cert = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-CRT-005"))
    if not app_cert:
        app_cert = Application(
            reference_code="PN-DEMO-CRT-005",
            user_id=user_cert.id,
            status="KYC_APPROVED",
            current_step=6,
            region="WEST",
            preferred_language="en",
            channel="DIRECT_PORTAL",
            full_name="Priya Patel",
            date_of_birth=datetime.date(1996, 7, 19),
            gender="FEMALE",
            mobile="+919722334455",
            email="posp_certified@policynest.demo",
            pan_number="ABCPA7766T",
            aadhaar_last4="9012",
            address_line1="Flat 401, Galaxy Enclave",
            city="Surat",
            state="Gujarat",
            pincode="395007",
            same_as_permanent=True,
            education_level="GRADUATE",
            account_holder_name="Priya Patel",
            bank_name="HDFC Bank",
            ifsc_code="HDFC0000123",
            account_number_last4="2345",
            account_number_masked="••••••••2345",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(days=2),
            submitted_at=now - datetime.timedelta(days=2),
        )
        session.add(app_cert)
        session.flush()

        tr_cert = TrainingRecord(
            application_id=app_cert.id,
            eligibility_status="ELIGIBLE",
            lms_provider="sandbox",
            is_simulated=True,
            enrollment_status="COMPLETED",
            required_hours=Decimal("15.00"),
            completed_hours=Decimal("15.00"),
            progress_pct=Decimal("100.00"),
            enrolled_at=now - datetime.timedelta(days=2),
            started_at=now - datetime.timedelta(days=2),
            completed_at=now - datetime.timedelta(days=1),
            exam_status="PASSED",
            exam_score_pct=Decimal("88.00"),
            exam_attempts=1,
            last_exam_at=now - datetime.timedelta(days=1),
            certification_status="CERTIFIED",
            certificate_number="POSP-2026-CERT-8841",
            certified_at=now - datetime.timedelta(days=1),
            certificate_valid_until=now + datetime.timedelta(days=365 * 3),
        )
        session.add(tr_cert)

    scenarios.append(
        {
            "id": str(app_cert.id),
            "reference_code": "PN-DEMO-CRT-005",
            "scenario": "Certified POSP",
            "status": "CERTIFIED",
            "applicant": "Priya Patel",
            "login": "posp_certified@policynest.demo",
            "highlight": "15 hours LMS completed, exam score 88%, verifiable IRDAI certificate code POSP-2026-CERT-8841.",
        }
    )

    # --- Scenario 6: Vernacular Hindi Candidate & State Board Marksheet ---
    user_reg = created_users["posp_regional@policynest.demo"]
    app_reg = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-REG-006"))
    if not app_reg:
        app_reg = Application(
            reference_code="PN-DEMO-REG-006",
            user_id=user_reg.id,
            status="KYC_APPROVED",
            current_step=6,
            region="EAST",
            preferred_language="hi",
            channel="DIRECT_PORTAL",
            full_name="Ananya Das",
            date_of_birth=datetime.date(1997, 10, 5),
            gender="FEMALE",
            father_or_spouse_name="Subhash Das",
            mobile="+919833445566",
            email="posp_regional@policynest.demo",
            pan_number="ABCPA4321Q",
            aadhaar_last4="5432",
            address_line1="Boring Road, Anandpuri",
            city="Patna",
            state="Bihar",
            pincode="800001",
            same_as_permanent=True,
            education_level="HIGHER_SECONDARY",
            board_name="Bihar School Examination Board (BSEB)",
            passing_year=2015,
            account_holder_name="Ananya Das",
            bank_name="Bank of India",
            ifsc_code="BKID0004401",
            account_number_last4="2233",
            account_number_masked="••••••••2233",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(hours=4),
            submitted_at=now - datetime.timedelta(hours=4),
        )
        session.add(app_reg)
        session.flush()

        exec_reg = RuleExecution(
            application_id=app_reg.id,
            ruleset_id=active_ruleset.id,
            ruleset_version=active_ruleset.version,
            trigger_source="APPLICATION_SUBMIT",
            outcome="AUTO_APPROVE",
            recommended_status="APPROVED",
            eligibility_status="PASS",
            completeness_status="PASS",
            consistency_status="PASS",
            risk_level="LOW",
            auto_pass_eligible=True,
            requires_human_review=False,
            reason_codes=["STATE_BOARD_VERIFIED", "VERNACULAR_LOCALIZATION_OK"],
            rule_results=[],
            rework_items=[],
            risk_indicators=[],
            summary="State secondary board credential validated and regional vernacular profile configured.",
            executed_at=now - datetime.timedelta(hours=4),
        )
        session.add(exec_reg)

    scenarios.append(
        {
            "id": str(app_reg.id),
            "reference_code": "PN-DEMO-REG-006",
            "scenario": "Vernacular Hindi & State Board",
            "status": "KYC_APPROVED",
            "applicant": "Ananya Das",
            "login": "posp_regional@policynest.demo",
            "highlight": "Vernacular Hindi preferred, Bihar State Board marksheet verified, enrolled in Hindi modules.",
        }
    )

    # --- Scenario 7: Adverse Decision Appeal Under Review ---
    user_apl = created_users["posp_appeal@policynest.demo"]
    app_apl = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-APL-007"))
    if not app_apl:
        app_apl = Application(
            reference_code="PN-DEMO-APL-007",
            user_id=user_apl.id,
            status="IN_REVIEW",
            current_step=6,
            region="NORTH",
            preferred_language="en",
            channel="DIRECT_PORTAL",
            full_name="Kavita Verma",
            date_of_birth=datetime.date(1991, 4, 18),
            gender="FEMALE",
            father_or_spouse_name="Vikas Verma",
            mobile="+919877001122",
            email="posp_appeal@policynest.demo",
            pan_number="ABCPS6543Z",
            aadhaar_last4="8765",
            address_line1="C-4, Lajpat Nagar",
            city="New Delhi",
            state="Delhi",
            pincode="110024",
            same_as_permanent=True,
            education_level="GRADUATE",
            board_name="Delhi University",
            passing_year=2012,
            account_holder_name="Kavita Verma",
            bank_name="Axis Bank",
            ifsc_code="UTIB0000005",
            account_number_last4="9911",
            account_number_masked="••••••••9911",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(days=1),
            submitted_at=now - datetime.timedelta(days=1),
        )
        session.add(app_apl)
        session.flush()

        dec_apl = ApplicationDecision(
            application_id=app_apl.id,
            decided_by_user_id=reviewer_user.id,
            decided_by_role="REVIEWER",
            decision="REJECTED",
            previous_status="IN_REVIEW",
            new_status="REJECTED",
            is_override=False,
            reason_codes=["NAME_MISMATCH_PAN_VS_BANK"],
            reason_text="PAN holder name 'Kavita Sharma' differs from bank account holder 'Kavita Verma'.",
            rework_items=[],
            created_at=now - datetime.timedelta(hours=18),
        )
        session.add(dec_apl)
        session.flush()

        appeal_record = ApplicationAppeal(
            application_id=app_apl.id,
            submitted_by_user_id=user_apl.id,
            status="OPEN",
            appeal_reason="Legal surname change post marriage from Sharma to Verma.",
            supporting_notes="Uploaded Government Gazette notification and Marriage Certificate registration #DL-2024-MC-8812.",
        )
        session.add(appeal_record)

    scenarios.append(
        {
            "id": str(app_apl.id),
            "reference_code": "PN-DEMO-APL-007",
            "scenario": "Adverse Decision Appeal",
            "status": "APPEAL_OPEN",
            "applicant": "Kavita Verma",
            "login": "posp_appeal@policynest.demo",
            "highlight": "Phase 4 statutory appeal workflow with legal gazetted name change proof attached for supervisor.",
        }
    )

    # --- Scenario 8: Complex Indian Name 8-Tier Token Permutation Match ---
    user_bnk = created_users["posp_bank@policynest.demo"]
    app_bnk = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-BNK-008"))
    if not app_bnk:
        app_bnk = Application(
            reference_code="PN-DEMO-BNK-008",
            user_id=user_bnk.id,
            status="KYC_APPROVED",
            current_step=6,
            region="SOUTH",
            preferred_language="en",
            channel="DIRECT_PORTAL",
            full_name="Mohammed Abdul Rahman Siddiqui",
            date_of_birth=datetime.date(1993, 12, 1),
            gender="MALE",
            father_or_spouse_name="Abdul Rahman Siddiqui",
            mobile="+919944556677",
            email="posp_bank@policynest.demo",
            pan_number="XYZPS9876M",
            aadhaar_last4="6543",
            address_line1="Banjara Hills Road 12",
            city="Hyderabad",
            state="Telangana",
            pincode="500034",
            same_as_permanent=True,
            education_level="GRADUATE",
            board_name="Osmania University",
            passing_year=2014,
            account_holder_name="Mohammed Abdul Rahman Siddiqui",
            bank_name="ICICI Bank",
            ifsc_code="ICIC0000047",
            account_number_last4="7744",
            account_number_masked="••••••••7744",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(hours=6),
            submitted_at=now - datetime.timedelta(hours=6),
        )
        session.add(app_bnk)
        session.flush()

        exec_bnk = RuleExecution(
            application_id=app_bnk.id,
            ruleset_id=active_ruleset.id,
            ruleset_version=active_ruleset.version,
            trigger_source="APPLICATION_SUBMIT",
            outcome="AUTO_APPROVE",
            recommended_status="APPROVED",
            eligibility_status="PASS",
            completeness_status="PASS",
            consistency_status="PASS",
            risk_level="LOW",
            auto_pass_eligible=True,
            requires_human_review=False,
            reason_codes=[
                "TIER_5_TOKEN_PERMUTATION_MATCH",
                "BANK_PENNY_DROP_ACRONYM_RESOLVED",
            ],
            rule_results=[],
            rework_items=[],
            risk_indicators=[],
            summary="Multi-part name acronym resolved by 8-tier Indian name consistency engine.",
            executed_at=now - datetime.timedelta(hours=6),
        )
        session.add(exec_bnk)

    scenarios.append(
        {
            "id": str(app_bnk.id),
            "reference_code": "PN-DEMO-BNK-008",
            "scenario": "Multi-Word Name Permutation",
            "status": "KYC_APPROVED",
            "applicant": "Mohammed Abdul Rahman Siddiqui",
            "login": "posp_bank@policynest.demo",
            "highlight": "8-Tier Indian name engine resolved bank beneficiary acronym 'M A R SIDDIQUI' with 88% confidence.",
        }
    )

    # --- Scenario 9: Mid-Module Active LMS Training ---
    user_tr = created_users["posp_training@policynest.demo"]
    app_tr = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-LMS-009"))
    if not app_tr:
        app_tr = Application(
            reference_code="PN-DEMO-LMS-009",
            user_id=user_tr.id,
            status="TRAINING_IN_PROGRESS",
            current_step=6,
            region="NORTH",
            preferred_language="en",
            channel="DIRECT_PORTAL",
            full_name="Deepak Joshi",
            date_of_birth=datetime.date(1994, 9, 12),
            gender="MALE",
            father_or_spouse_name="Harish Joshi",
            mobile="+919899112233",
            email="posp_training@policynest.demo",
            pan_number="ABCPA3344K",
            aadhaar_last4="4321",
            address_line1="Rajpur Road",
            city="Dehradun",
            state="Uttarakhand",
            pincode="248001",
            same_as_permanent=True,
            education_level="GRADUATE",
            board_name="Uttarakhand Technical University",
            passing_year=2016,
            account_holder_name="Deepak Joshi",
            bank_name="Canara Bank",
            ifsc_code="CNRB0001234",
            account_number_last4="5511",
            account_number_masked="••••••••5511",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(days=2),
            submitted_at=now - datetime.timedelta(days=2),
        )
        session.add(app_tr)
        session.flush()

        tr_active = TrainingRecord(
            application_id=app_tr.id,
            user_id=user_tr.id,
            course_code="IRDAI-POSP-15H",
            course_title="15-Hour Mandatory POSP General & Life Insurance Certification",
            eligibility_status="ELIGIBLE",
            lms_provider="sandbox",
            is_simulated=True,
            enrollment_status="IN_PROGRESS",
            required_hours=Decimal("15.00"),
            completed_hours=Decimal("8.50"),
            progress_pct=Decimal("56.67"),
            enrolled_at=now - datetime.timedelta(days=1),
            started_at=now - datetime.timedelta(hours=14),
            exam_status="NOT_ATTEMPTED",
            certification_status="PENDING_EXAM",
        )
        session.add(tr_active)

    scenarios.append(
        {
            "id": str(app_tr.id),
            "reference_code": "PN-DEMO-LMS-009",
            "scenario": "LMS Training (56% Complete)",
            "status": "TRAINING_IN_PROGRESS",
            "applicant": "Deepak Joshi",
            "login": "posp_training@policynest.demo",
            "highlight": "8.5 / 15.0 hours logged. 3 modules completed, ready to resume module 4 and take practice test.",
        }
    )

    # --- Scenario 10: IRDAI 18-Year Minimum Age Boundary Validation ---
    user_age = created_users["posp_age@policynest.demo"]
    app_age = session.scalar(select(Application).where(Application.reference_code == "PN-DEMO-AGE-010"))
    if not app_age:
        age_18_dob = (now - datetime.timedelta(days=(18 * 365 + 5))).date()
        app_age = Application(
            reference_code="PN-DEMO-AGE-010",
            user_id=user_age.id,
            status="KYC_APPROVED",
            current_step=6,
            region="SOUTH",
            preferred_language="en",
            channel="DIRECT_PORTAL",
            full_name="Aditya Varma",
            date_of_birth=age_18_dob,
            gender="MALE",
            father_or_spouse_name="Kishore Varma",
            mobile="+919847009988",
            email="posp_age@policynest.demo",
            pan_number="ABCPA1122D",
            aadhaar_last4="9876",
            address_line1="Marine Drive",
            city="Kochi",
            state="Kerala",
            pincode="682031",
            same_as_permanent=True,
            education_level="HIGHER_SECONDARY",
            board_name="Kerala State Board",
            passing_year=now.year - 1,
            account_holder_name="Aditya Varma",
            bank_name="Federal Bank",
            ifsc_code="FDRL0001001",
            account_number_last4="3322",
            account_number_masked="••••••••3322",
            consent_terms=True,
            consent_kyc_processing=True,
            declaration_no_other_posp=True,
            declared_at=now - datetime.timedelta(hours=1),
            submitted_at=now - datetime.timedelta(hours=1),
        )
        session.add(app_age)
        session.flush()

        exec_age = RuleExecution(
            application_id=app_age.id,
            ruleset_id=active_ruleset.id,
            ruleset_version=active_ruleset.version,
            trigger_source="APPLICATION_SUBMIT",
            outcome="AUTO_APPROVE",
            recommended_status="APPROVED",
            eligibility_status="PASS",
            completeness_status="PASS",
            consistency_status="PASS",
            risk_level="LOW",
            auto_pass_eligible=True,
            requires_human_review=False,
            reason_codes=[
                "MINIMUM_AGE_18_COMPLIANT",
                "CLASS_10_QUALIFICATION_VALID",
            ],
            rule_results=[],
            rework_items=[],
            risk_indicators=[],
            summary="Candidate meets IRDAI minimum age statutory requirement exactly on DOB boundary.",
            executed_at=now - datetime.timedelta(hours=1),
        )
        session.add(exec_age)

    scenarios.append(
        {
            "id": str(app_age.id),
            "reference_code": "PN-DEMO-AGE-010",
            "scenario": "Age 18 Boundary Compliance",
            "status": "KYC_APPROVED",
            "applicant": "Aditya Varma",
            "login": "posp_age@policynest.demo",
            "highlight": "Candidate exactly 18 years old. Automated IRDAI Guidelines 2016 statutory age rule passed.",
        }
    )

    session.commit()

    return {
        "status": "SUCCESS",
        "demo_password": DEMO_PASSWORD,
        "users_count": len(DEMO_ACCOUNTS),
        "scenarios_seeded": len(scenarios),
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PolicyNest Demo & Evaluation Scenario Seeder")
    parser.add_argument("--reset", action="store_true", help="Purge previous demo records before seeding")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        try:
            res = seed_demo_data(session, reset=args.reset)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print("\n=======================================================")
                print("   PolicyNest Live Evaluation & Demo Scenarios Seeded  ")
                print("=======================================================")
                print(f"Universal Demo Password: {res['demo_password']}\n")
                print("Key Evaluator & Staff Accounts:")
                print(" - Reviewer Officer: reviewer@policynest.demo")
                print(" - Operations Lead:  admin@policynest.demo\n")
                print("Demonstration Pipeline Scenarios:")
                for s in res["scenarios"]:
                    print(f" • [{s['reference_code']}] {s['scenario']}")
                    print(f"   Applicant: {s['applicant']} ({s['login']})")
                    print(f"   Status:    {s['status']}")
                    print(f"   Features:  {s['highlight']}\n")
                print("=======================================================\n")
            return 0
        except Exception as exc:
            logger.exception("Failed to seed demo data: %s", exc)
            if args.json:
                print(json.dumps({"status": "FAILED", "error": str(exc)}, indent=2))
            return 1


if __name__ == "__main__":
    sys.exit(main())
