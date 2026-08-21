"""Tool tests: document classify+store (duplicate detection), reminders, escalations."""

import hashlib
import pytest

from app.tools.documents import classify_document, store_document
from app.tools.errors import (
    DuplicateDocumentError,
    EscalationNotOpenError,
    PatientNotFoundError,
    ReminderValidationError,
    WorkflowRunNotFoundError,
)
from app.tools.escalations import create_escalation, resolve_escalation
from app.tools.reminders import create_reminder
from tests.unit.factories import audit_count, make_patient, make_user
from app.db.models import WorkflowRun
from datetime import datetime, timedelta, timezone


def test_classify_document_types():
    assert classify_document("ecg_report.pdf") == "ecg"
    assert classify_document("ecg_report.pdf", b"12-lead electrocardiogram") == "ecg"
    assert classify_document("blood_panel_lab.pdf") == "lab_report"
    assert classify_document("referral_letter.pdf") == "referral"
    assert classify_document("mri_scan.pdf") == "imaging"
    assert classify_document("prescription.pdf") == "prescription"
    assert classify_document("passport_scan.pdf") == "id_proof"
    assert classify_document("random_notes.txt", b"nothing relevant here") == "other"


def test_store_document_and_duplicate_detection(db, tmp_path):
    patient = make_patient(db)
    content = b"%PDF-1.4 fake ecg content"
    doc = store_document(
        db,
        patient.id,
        "ecg_report_2026.pdf",
        content,
        upload_dir=str(tmp_path),
    )
    assert doc.document_type == "ecg"
    assert doc.checksum == hashlib.sha256(content).hexdigest()
    assert (tmp_path / f"patient_{patient.id}" / "ecg_report_2026.pdf").exists()
    assert audit_count(db, "document.uploaded") == 1

    with pytest.raises(DuplicateDocumentError):
        store_document(
            db,
            patient.id,
            "ecg_report_2026.pdf",
            b"%PDF-1.4 fake ecg content",
            upload_dir=str(tmp_path),
        )
    assert audit_count(db, "document.uploaded.failed") == 1

    with pytest.raises(PatientNotFoundError):
        store_document(db, 999999, "x.pdf", b"data", upload_dir=str(tmp_path))


def test_create_reminder_and_validation(db):
    patient = make_patient(db)
    reminder = create_reminder(
        db,
        patient.id,
        reminder_type="appointment",
        scheduled_for=datetime.now(timezone.utc) + timedelta(days=1),
        message="Your appointment is tomorrow.",
    )
    assert reminder.status == "pending"
    assert reminder.patient_id == patient.id
    assert audit_count(db, "reminder.created") == 1

    with pytest.raises(PatientNotFoundError):
        create_reminder(db, 999999, scheduled_for=datetime.now(timezone.utc))

    with pytest.raises(ReminderValidationError):
        create_reminder(db, patient.id, reminder_type="bogus", scheduled_for=datetime.now(timezone.utc))


def test_create_and_resolve_escalation(db):
    patient = make_patient(db)
    staff = make_user(db, role="staff")
    workflow = WorkflowRun(
        patient_id=patient.id, request_text="Emergency language here", status="escalated"
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    esc = create_escalation(
        db,
        reason="emergency language detected",
        severity="high",
        details="Request contains acute symptom language.",
        workflow_run_id=workflow.id,
        patient_id=patient.id,
    )
    assert esc.status == "open"
    assert audit_count(db, "escalation.created") == 1

    resolved = resolve_escalation(db, esc.id, staff.id, "Contacted patient, no action needed.")
    assert resolved.status == "resolved"
    assert resolved.reviewed_by == staff.id
    assert resolved.resolved_at is not None
    assert audit_count(db, "escalation.resolved") == 1


def test_escalation_failures(db):
    with pytest.raises(WorkflowRunNotFoundError):
        create_escalation(db, "reason", workflow_run_id=999999)
    with pytest.raises(EscalationNotOpenError):
        resolve_escalation(db, 999999, 1, "notes")
    with pytest.raises(ValueError):
        create_escalation(db, "reason", severity="bogus")


def test_resolve_only_open_escalation_and_staff_reviewer(db):
    patient = make_patient(db)
    staff = make_user(db, role="staff")
    non_staff = make_user(db, role="patient")
    esc = create_escalation(db, "reason", patient_id=patient.id)

    with pytest.raises(ValueError):
        resolve_escalation(db, esc.id, non_staff.id, "notes")

    resolve_escalation(db, esc.id, staff.id, "done")
    with pytest.raises(EscalationNotOpenError):
        resolve_escalation(db, esc.id, staff.id, "again")