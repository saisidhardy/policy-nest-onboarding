from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import ExamAttempt
from app.services.training import MODULES, QUESTIONS
from tests.conftest import create_staff, csrf, login, register

REQUIRED_DOCUMENTS = ["PAN", "AADHAAR", "EDUCATION_10TH", "PHOTO", "SIGNATURE", "BANK_PROOF"]


def _verified_applicant(client, mailbox):
    assert register(client).status_code == 201
    token = mailbox.last_token("asha@example.com")
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200


def _complete_application(client):
    started = client.post("/api/v1/applications/mine", headers=csrf(client))
    assert started.status_code == 201, started.text
    saved = client.patch(
        "/api/v1/applications/mine",
        headers=csrf(client),
        json={
            "current_step": 3,
            "date_of_birth": "1990-05-12",
            "pan_number": "ABCPD1234E",
            "aadhaar_last4": "4321",
            "region": "NORTH",
            "address": {"line1": "12 Test Road", "city": "Delhi", "pincode": "110001"},
            "education": {"qualification": "Class 12"},
            "bank_details": {
                "account_holder": "Asha Verma",
                "account_number": "123456789012",
                "ifsc": "HDFC0001234",
            },
            "declarations": {
                "information_true": True,
                "data_processing_consent": True,
                "exclusivity_confirmed": True,
            },
        },
    )
    assert saved.status_code == 200, saved.text
    for document_type in REQUIRED_DOCUMENTS:
        uploaded = client.post(
            "/api/v1/applications/mine/documents",
            headers=csrf(client),
            data={"document_type": document_type},
            files={"file": (f"{document_type.lower()}.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
        )
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["status"] == "UPLOADED"
    return saved.json()["id"]


def test_complete_onboarding_review_training_and_certificate(make_client, mailbox):
    applicant = make_client()
    _verified_applicant(applicant, mailbox)
    application_id = _complete_application(applicant)

    verification = applicant.post(
        "/api/v1/applications/mine/verifications",
        headers=csrf(applicant),
        json={"verification_type": "PAN", "consent": True},
    )
    assert verification.status_code == 202, verification.text
    assert verification.json()["environment"] == "SANDBOX"
    assert verification.json()["status"] == "SANDBOX_RECORDED"
    assert verification.json()["result"]["verified"] is False

    submitted = applicant.post("/api/v1/applications/mine/submit", headers=csrf(applicant))
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "SUBMITTED"

    create_staff("REVIEWER", "south@policynest.in", "South Reviewer", region="SOUTH", clearance=1)
    out_of_region = make_client()
    assert login(out_of_region, "south@policynest.in").status_code == 200
    assert out_of_region.get("/api/v1/reviews/queue").json() == []
    denied_detail = out_of_region.get(f"/api/v1/reviews/{application_id}")
    assert denied_detail.status_code == 403
    denied_action = out_of_region.post(
        f"/api/v1/reviews/{application_id}/actions",
        headers=csrf(out_of_region),
        json={"action": "ASSIGN_TO_ME", "justification": "Attempting an out-of-region assignment."},
    )
    assert denied_action.status_code == 403

    applicant_review = applicant.get("/api/v1/reviews/queue")
    assert applicant_review.status_code == 403

    create_staff("REVIEWER", "reviewer@policynest.in", "Rita Reviewer", region="NORTH", clearance=1)
    reviewer = make_client()
    assert login(reviewer, "reviewer@policynest.in").status_code == 200
    queue = reviewer.get("/api/v1/reviews/queue")
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()] == [application_id]

    assigned = reviewer.post(
        f"/api/v1/reviews/{application_id}/actions",
        headers=csrf(reviewer),
        json={"action": "ASSIGN_TO_ME", "justification": "Initial document review started."},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "UNDER_REVIEW"

    correction = reviewer.post(
        f"/api/v1/reviews/{application_id}/actions",
        headers=csrf(reviewer),
        json={
            "action": "REQUEST_CORRECTION",
            "justification": "Please confirm the applicant address.",
            "issues": [{"code": "ADDRESS_CONFIRMATION", "message": "Confirm the current address."}],
        },
    )
    assert correction.status_code == 200, correction.text
    assert correction.json()["status"] == "CORRECTION_REQUIRED"

    resubmitted = applicant.post("/api/v1/applications/mine/submit", headers=csrf(applicant))
    assert resubmitted.status_code == 200, resubmitted.text
    assert resubmitted.json()["status"] == "SUBMITTED"
    reassigned = reviewer.post(
        f"/api/v1/reviews/{application_id}/actions",
        headers=csrf(reviewer),
        json={"action": "ASSIGN_TO_ME", "justification": "Corrected application review resumed."},
    )
    assert reassigned.status_code == 200, reassigned.text
    approved = reviewer.post(
        f"/api/v1/reviews/{application_id}/actions",
        headers=csrf(reviewer),
        json={"action": "APPROVE_KYC", "justification": "All required evidence is acceptable."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "KYC_APPROVED"

    modules = applicant.get("/api/v1/training/modules")
    assert modules.status_code == 200, modules.text
    assert len(modules.json()) == 4
    for module_code, (_, required_minutes) in MODULES.items():
        progress = applicant.put(
            f"/api/v1/training/modules/{module_code}",
            headers=csrf(applicant),
            json={"minutes_completed": required_minutes},
        )
        assert progress.status_code == 200, progress.text
        assert progress.json()["completed"] is True

    attempt = applicant.post("/api/v1/training/exam/start", headers=csrf(applicant))
    assert attempt.status_code == 201, attempt.text
    attempt_body = attempt.json()
    assert len(attempt_body["questions"]) == 50
    wrong_answers = {
        question["id"]: (QUESTIONS[question["id"]]["answer"] + 1) % len(QUESTIONS[question["id"]]["options"])
        for question in attempt_body["questions"]
    }
    failed = applicant.post(
        f"/api/v1/training/exam/{attempt_body['id']}/submit",
        headers=csrf(applicant),
        json={"answers": wrong_answers},
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["passed"] is False
    assert failed.json()["score_percent"] == 0

    cooldown = applicant.post("/api/v1/training/exam/start", headers=csrf(applicant))
    assert cooldown.status_code == 429, cooldown.text
    assert cooldown.json()["error"]["code"] == "EXAM_RETAKE_COOLDOWN"
    assert cooldown.json()["error"]["details"]["retry_after_seconds"] > 0

    with get_sessionmaker()() as db:
        previous = db.scalar(select(ExamAttempt).where(ExamAttempt.id == attempt_body["id"]))
        assert previous is not None
        previous.submitted_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.commit()

    attempt = applicant.post("/api/v1/training/exam/start", headers=csrf(applicant))
    assert attempt.status_code == 201, attempt.text
    attempt_body = attempt.json()
    assert attempt_body["attempt_number"] == 2
    answers = {question["id"]: QUESTIONS[question["id"]]["answer"] for question in attempt_body["questions"]}
    result = applicant.post(
        f"/api/v1/training/exam/{attempt_body['id']}/submit",
        headers=csrf(applicant),
        json={"answers": answers},
    )
    assert result.status_code == 200, result.text
    assert result.json()["passed"] is True
    assert result.json()["score_percent"] == 100
    assert result.json()["certificate_number"].startswith("IRDAI-POSP-")

    certificate = applicant.get("/api/v1/training/certificate.pdf")
    assert certificate.status_code == 200
    assert certificate.headers["content-type"] == "application/pdf"
    assert certificate.content.startswith(b"%PDF-1.4")

    public = make_client()
    verification = public.get(f"/api/v1/training/certificates/{result.json()['certificate_number']}")
    assert verification.status_code == 200, verification.text
    assert verification.json()["status"] == "ACTIVE"
    assert verification.json()["candidate_name"] == "A*** V****"
    assert len(verification.json()["seal_sha256"]) == 64
    missing = public.get("/api/v1/training/certificates/IRDAI-POSP-UNKNOWN")
    assert missing.status_code == 404

    create_staff("SENIOR_REVIEWER", "senior@policynest.in", "Sunil Senior", region="ALL", clearance=3)
    operations = make_client()
    assert login(operations, "senior@policynest.in").status_code == 200
    summary = operations.get("/api/v1/operations/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["total_applications"] == 1
    assert summary.json()["by_status"]["CERTIFIED"] == 1
    assert summary.json()["certificates_issued"] == 1
    assert summary.json()["verification_statuses"]["SANDBOX_RECORDED"] == 1
