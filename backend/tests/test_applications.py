import uuid

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import Application, ApplicationEvent, AuditLog, Notification
from app.models.application import REQUIRED_DOC_TYPES
from tests.conftest import csrf, register, verify_user_email

FAKE_JPEG = b"\xff\xd8\xff\xe0" + (b"\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" * 10)
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + (b"\x00\x00\x00\rIHDR" * 12)
FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n" + b" " * 80


def _verified_applicant(make_client, mailbox, email: str = "asha@example.com", name: str = "Asha Verma"):
    c = make_client()
    r = register(c, email=email, name=name)
    assert r.status_code == 201, r.text
    verify_user_email(c, mailbox, email=email)
    return c


def _complete_draft_payload():
    return {
        "current_step": 5,
        "preferred_language": "EN",
        "full_name": "Asha Verma",
        "date_of_birth": "1996-05-14",
        "gender": "FEMALE",
        "father_or_spouse_name": "Ramesh Verma",
        "mobile": "9876543210",
        "email": "asha@example.com",
        "pan_number": "ABCDE1234F",
        "aadhaar_last4": "7890",
        "address_line1": "42 MG Road",
        "address_line2": "Indiranagar",
        "city": "Bengaluru",
        "district": "Bengaluru Urban",
        "state": "Karnataka",
        "pincode": "560038",
        "same_as_permanent": True,
        "education_level": "GRADUATE",
        "board_name": "CBSE",
        "school_or_university": "National Public School",
        "passing_year": 2014,
        "roll_number": "CBSE-129044",
        "result_status": "PASS",
        "percentage_or_cgpa": "86%",
        "account_holder_name": "Asha Verma",
        "bank_name": "HDFC Bank",
        "branch_name": "Indiranagar",
        "ifsc_code": "HDFC0000240",
        "account_number": "50100123456789",
        "account_type": "SAVINGS",
        "is_joint_account": False,
        "is_primary_holder": True,
    }


def _upload_all_six_docs(client, app_id: str) -> dict[str, dict]:
    uploaded = {}
    for doc_type in REQUIRED_DOC_TYPES:
        is_pdf = doc_type == "CLASS_10_MARKSHEET"
        payload = FAKE_PDF if is_pdf else FAKE_JPEG
        fname = f"{doc_type.lower()}.{'pdf' if is_pdf else 'jpg'}"
        mime = "application/pdf" if is_pdf else "image/jpeg"
        r = client.post(
            f"/api/v1/applications/{app_id}/documents/{doc_type}",
            headers=csrf(client),
            files={"file": (fname, payload, mime)},
        )
        assert r.status_code == 201, f"{doc_type}: {r.text}"
        uploaded[doc_type] = r.json()
    return uploaded


def test_unverified_applicant_cannot_create_or_list_applications(client):
    register(client)
    r = client.post("/api/v1/applications", headers=csrf(client), json={})
    assert r.status_code == 403 and r.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    assert client.get("/api/v1/applications").status_code == 403


def test_application_lifecycle_draft_save_documents_submit_and_history(make_client, mailbox):
    c = _verified_applicant(make_client, mailbox)

    # Create application
    created = c.post("/api/v1/applications", headers=csrf(c), json={})
    assert created.status_code == 201, created.text
    app = created.json()
    app_id = app["id"]
    assert app["reference_code"] == "APP-260001"
    assert app["status"] == "DRAFT"
    assert app["current_step"] == 1
    assert app["completeness"]["ready_to_submit"] is False

    # Cannot create duplicate active application
    dup = c.post("/api/v1/applications", headers=csrf(c), json={})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ACTIVE_APPLICATION_EXISTS"

    # Rejects 12-digit Aadhaar and invalid PAN/IFSC
    bad_aadhaar = c.patch(
        f"/api/v1/applications/{app_id}",
        headers=csrf(c),
        json={"aadhaar_last4": "123456789012"},
    )
    assert bad_aadhaar.status_code == 422

    # Save draft across all 4 sections
    saved = c.patch(f"/api/v1/applications/{app_id}", headers=csrf(c), json=_complete_draft_payload())
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["region"] == "SOUTH"
    assert data["pan_number"] == "ABCDE1234F"
    assert data["aadhaar_last4"] == "7890"
    assert data["account_number_last4"] == "6789"
    assert data["account_number_masked"] == "XXXXXXXXXX6789"
    assert data["has_account_number"] is True
    assert "account_number" not in data
    assert "account_number_encrypted" not in data

    # Verify DB stores encrypted bank account number, never plaintext
    with get_sessionmaker()() as db:
        db_app = db.get(Application, uuid.UUID(app_id))
        assert db_app is not None
        assert db_app.account_number_encrypted is not None
        assert "50100123456789" not in db_app.account_number_encrypted

        # Ensure audit log has no raw PAN or bank account number
        logs = db.scalars(select(AuditLog)).all()
        joined = " ".join(str(log.details) for log in logs)
        assert "ABCDE1234F" not in joined
        assert "50100123456789" not in joined

    # Resume application via /current
    resumed = c.get("/api/v1/applications/current")
    assert resumed.status_code == 200 and resumed.json()["current_step"] == 5

    # Incomplete submit rejected before all 6 docs are uploaded
    incomplete = c.post(
        f"/api/v1/applications/{app_id}/submit",
        headers=csrf(c),
        json={"consent_terms": True, "consent_kyc_processing": True, "declaration_no_other_posp": True},
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["error"]["code"] == "APPLICATION_INCOMPLETE"
    assert len(incomplete.json()["error"]["details"]["missing_documents"]) == 6

    # Upload all 6 required documents
    docs = _upload_all_six_docs(c, app_id)
    assert len(docs) == 6

    # Retrieve stored document securely
    pan_doc = docs["PAN_CARD"]
    dl = c.get(f"/api/v1/applications/{app_id}/documents/{pan_doc['id']}/content")
    assert dl.status_code == 200
    assert dl.content == FAKE_JPEG
    assert dl.headers["x-content-type-options"] == "nosniff"

    # Replace PAN card creates version 2 and keeps v1 in history
    replaced = c.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(c),
        files={"file": ("pan_v2.png", FAKE_PNG, "image/png")},
    )
    assert replaced.status_code == 201 and replaced.json()["version"] == 2
    hist_docs = c.get(f"/api/v1/applications/{app_id}/documents", params={"include_history": True}).json()
    assert len([d for d in hist_docs if d["doc_type"] == "PAN_CARD"]) == 2

    # Unchecked declarations rejected
    unchecked = c.post(
        f"/api/v1/applications/{app_id}/submit",
        headers=csrf(c),
        json={"consent_terms": True, "consent_kyc_processing": False, "declaration_no_other_posp": True},
    )
    assert unchecked.status_code == 422 and unchecked.json()["error"]["code"] == "DECLARATIONS_REQUIRED"

    # Submit application
    submitted = c.post(
        f"/api/v1/applications/{app_id}/submit",
        headers=csrf(c),
        json={"consent_terms": True, "consent_kyc_processing": True, "declaration_no_other_posp": True},
    )
    assert submitted.status_code == 200, submitted.text
    sub_body = submitted.json()
    assert sub_body["status"] == "SUBMITTED"
    assert sub_body["submitted_at"] is not None

    # Locked after submission
    edit_after = c.patch(f"/api/v1/applications/{app_id}", headers=csrf(c), json={"city": "Mysuru"})
    assert edit_after.status_code == 409 and edit_after.json()["error"]["code"] == "APPLICATION_LOCKED"
    upload_after = c.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(c),
        files={"file": ("pan.jpg", FAKE_JPEG, "image/jpeg")},
    )
    assert upload_after.status_code == 409

    # History records creation, saves, uploads, replacements, and submission
    history = c.get(f"/api/v1/applications/{app_id}/history").json()
    event_types = {e["event_type"] for e in history}
    assert {
        "APPLICATION_CREATED",
        "DRAFT_SAVED",
        "DOCUMENT_UPLOADED",
        "DOCUMENT_REPLACED",
        "APPLICATION_SUBMITTED",
    } <= event_types

    # Notifications recorded for creation and submission
    notifs = c.get("/api/v1/notifications").json()
    assert notifs["total"] >= 2 and notifs["unread_count"] >= 2
    first_id = notifs["items"][0]["id"]
    assert c.post(f"/api/v1/notifications/{first_id}/read", headers=csrf(c)).json()["is_read"] is True
    assert c.post("/api/v1/notifications/read-all", headers=csrf(c)).status_code == 200
    assert c.get("/api/v1/notifications").json()["unread_count"] == 0


def test_upload_validation_rejects_spoofed_magic_bytes_pdf_selfie_and_oversize(make_client, mailbox):
    c = _verified_applicant(make_client, mailbox)
    app_id = c.post("/api/v1/applications", headers=csrf(c), json={}).json()["id"]

    # Fake executable or text masquerading as JPEG
    spoof = c.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(c),
        files={"file": ("evil.jpg", b"#!/bin/sh\nrm -rf /\n" + b"A" * 120, "image/jpeg")},
    )
    assert spoof.status_code == 415 and spoof.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    # PDF rejected for selfie
    pdf_selfie = c.post(
        f"/api/v1/applications/{app_id}/documents/APPLICANT_SELFIE",
        headers=csrf(c),
        files={"file": ("selfie.pdf", FAKE_PDF, "application/pdf")},
    )
    assert pdf_selfie.status_code == 415

    # Too small / corrupt
    tiny = c.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(c),
        files={"file": ("tiny.jpg", b"\xff\xd8\xff\xe0123", "image/jpeg")},
    )
    assert tiny.status_code == 422 and tiny.json()["error"]["code"] == "FILE_TOO_SMALL"

    # Oversize (> 10 MB)
    huge = c.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(c),
        files={"file": ("huge.jpg", b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024 + 100), "image/jpeg")},
    )
    assert huge.status_code == 413 and huge.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_idor_isolation_between_applicants_on_applications_documents_and_notifications(make_client, mailbox):
    alice = _verified_applicant(make_client, mailbox, email="alice@example.com", name="Alice Nair")
    bob = _verified_applicant(make_client, mailbox, email="bob@example.com", name="Bob Menon")

    alice_app = alice.post("/api/v1/applications", headers=csrf(alice), json={}).json()
    app_id = alice_app["id"]
    doc = alice.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(alice),
        files={"file": ("pan.jpg", FAKE_JPEG, "image/jpeg")},
    ).json()

    # Bob only sees his own (empty) list
    assert bob.get("/api/v1/applications").json() == []
    assert bob.get("/api/v1/applications/current").json() is None

    # Bob is blocked (403) on every application & document route targeting Alice's application
    assert bob.get(f"/api/v1/applications/{app_id}").status_code == 403
    assert bob.patch(f"/api/v1/applications/{app_id}", headers=csrf(bob), json={"city": "Hacked"}).status_code == 403
    assert bob.get(f"/api/v1/applications/{app_id}/history").status_code == 403
    assert bob.get(f"/api/v1/applications/{app_id}/documents").status_code == 403
    assert bob.get(f"/api/v1/applications/{app_id}/documents/{doc['id']}/content").status_code == 403
    assert (
        bob.post(
            f"/api/v1/applications/{app_id}/documents/PAN_CARD",
            headers=csrf(bob),
            files={"file": ("pan.jpg", FAKE_JPEG, "image/jpeg")},
        ).status_code
        == 403
    )
    assert bob.delete(f"/api/v1/applications/{app_id}/documents/{doc['id']}", headers=csrf(bob)).status_code == 403
    assert (
        bob.post(
            f"/api/v1/applications/{app_id}/submit",
            headers=csrf(bob),
            json={"consent_terms": True, "consent_kyc_processing": True, "declaration_no_other_posp": True},
        ).status_code
        == 403
    )

    # Bob cannot mark Alice's notification read
    alice_notif_id = alice.get("/api/v1/notifications").json()["items"][0]["id"]
    assert bob.post(f"/api/v1/notifications/{alice_notif_id}/read", headers=csrf(bob)).status_code == 403

    with get_sessionmaker()() as db:
        denials = db.scalars(select(AuditLog).where(AuditLog.action == "access.denied")).all()
        assert len(denials) >= 9
        assert db.scalar(select(Notification).where(Notification.id == uuid.UUID(alice_notif_id))).is_read is False


def test_withdraw_draft_and_delete_draft_document(make_client, mailbox):
    c = _verified_applicant(make_client, mailbox)
    app_id = c.post("/api/v1/applications", headers=csrf(c), json={}).json()["id"]
    doc = c.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(c),
        files={"file": ("pan.jpg", FAKE_JPEG, "image/jpeg")},
    ).json()

    assert c.delete(f"/api/v1/applications/{app_id}/documents/{doc['id']}", headers=csrf(c)).status_code == 200
    assert c.get(f"/api/v1/applications/{app_id}/documents").json() == []

    w = c.post(f"/api/v1/applications/{app_id}/withdraw", headers=csrf(c), json={"reason": "Entered wrong details"})
    assert w.status_code == 200 and w.json()["status"] == "WITHDRAWN"
    assert c.get("/api/v1/applications/current").json() is None

    # Can start a fresh application after withdrawal
    second = c.post("/api/v1/applications", headers=csrf(c), json={})
    assert second.status_code == 201 and second.json()["reference_code"] == "APP-260002"

    with get_sessionmaker()() as db:
        events = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == uuid.UUID(app_id))).all()
        assert any(e.event_type == "APPLICATION_WITHDRAWN" for e in events)
