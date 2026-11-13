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
import sys
from decimal import Decimal

# Ensure fallback settings for standalone invocation
os.environ.setdefault("SECRET_KEY", "cutover-verification-ephemeral-key-min-32-chars")
os.environ.setdefault("DATABASE_URL", "sqlite:///./policynest_local.db")

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_sessionmaker
from app.core.security import hash_password
from app.models.application import Application
from app.models.base import utcnow
from app.models.rules import ApplicationDecision, RuleExecution
from app.models.training import TrainingRecord
from app.models.user import Role, User

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
            ruleset_version=1,
            outcome="PASS",
            executed_at=now - datetime.timedelta(hours=2),
            reasons_evaluated=["ALL_CRITERIA_MET", "0_MISMATCH", "PAN_BANK_VERIFIED"],
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
            decision="NEEDS_MORE_INFO",
            previous_status="IN_REVIEW",
            new_status="NEEDS_MORE_INFO",
            reason_codes=["CLASS_10_MARKSHEET_BLURRED", "NAME_PARTIALLY_CROPPED"],
            reason_text=(
                "Class 10 mark sheet lower border is cropped and passing year is blurred. "
                "कृपया कक्षा 10 की अंकतालिका को स्पष्ट रूप से स्कैन करके पुनः अपलोड करें।"
            ),
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
