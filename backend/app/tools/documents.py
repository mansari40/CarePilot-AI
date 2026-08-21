"""Document coordination tool — classify, checksum, dedupe and store uploads."""

import hashlib
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import PatientDocument, PatientProfile
from app.tools.audit import log_audit
from app.tools.errors import DuplicateDocumentError, PatientNotFoundError

_CLASSIFIER_RULES: list[tuple[str, re.Pattern]] = [
    ("ecg", re.compile(r"\b(ecg|ekg|electrocardiogram|12-lead)\b", re.IGNORECASE)),
    ("lab_report", re.compile(r"\b(lab|blood panel|test result|pathology|lipid|glucose)\b", re.IGNORECASE)),
    ("prescription", re.compile(r"\b(prescri|rx|medication list)", re.IGNORECASE)),
    ("referral", re.compile(r"\b(referral|referr|request form|consult note)\b", re.IGNORECASE)),
    ("id_proof", re.compile(r"\b(passport|id card|driving license|id proof)\b", re.IGNORECASE)),
    ("imaging", re.compile(r"\b(mri|ct scan|x-?ray|ultrasound|imaging|scan)\b", re.IGNORECASE)),
]


def classify_document(filename: str, content: str | bytes | None = None) -> str:
    """Classify a document by filename and optional text content."""
    text_content = ""
    if isinstance(content, bytes):
        text_content = content.decode("utf-8", errors="ignore")
    elif content:
        text_content = content

    haystack = f"{filename} {text_content[:2000]}".replace("_", " ")
    for doc_type, pattern in _CLASSIFIER_RULES:
        if pattern.search(haystack):
            return doc_type
    return "other"


def store_document(
    session: Session,
    patient_id: int,
    filename: str,
    content: bytes,
    document_type: str | None = None,
    appointment_id: int | None = None,
    actor_user_id: int | None = None,
    upload_dir: str | None = None,
) -> PatientDocument:
    action = "document.uploaded"
    try:
        if session.get(PatientProfile, patient_id) is None:
            raise PatientNotFoundError(f"No patient profile with id {patient_id}")

        checksum = hashlib.sha256(content).hexdigest()
        duplicate = (
            session.query(PatientDocument)
            .filter(
                PatientDocument.patient_id == patient_id,
                PatientDocument.checksum == checksum,
            )
            .first()
        )
        if duplicate is not None:
            raise DuplicateDocumentError(
                f"Patient {patient_id} already has a document with checksum {checksum[:12]}... "
                f"(existing document id {duplicate.id})"
            )

        classified = document_type or classify_document(filename, content)
        root = Path(upload_dir or get_settings().upload_dir)
        patient_dir = root / f"patient_{patient_id}"
        patient_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        storage_path = patient_dir / safe_name
        storage_path.write_bytes(content)

        document = PatientDocument(
            patient_id=patient_id,
            appointment_id=appointment_id,
            filename=safe_name,
            storage_path=str(storage_path),
            document_type=classified,
            checksum=checksum,
            is_duplicate=False,
        )
        session.add(document)
        session.flush()
        log_audit(
            session,
            action,
            "PatientDocument",
            entity_id=document.id,
            details={
                "filename": safe_name,
                "document_type": classified,
                "checksum": checksum[:12],
                "size_bytes": len(content),
            },
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(document)
        return document
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "PatientDocument",
            details={"patient_id": patient_id, "filename": filename, "reason": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise


def attach_document_to_appointment(
    session: Session,
    document_id: int,
    appointment_id: int,
    actor_user_id: int | None = None,
) -> PatientDocument:
    """Attach a verified patient document to the booked appointment."""
    action = "document.attached"
    try:
        document = session.get(PatientDocument, document_id)
        if document is None:
            raise ValueError(f"No document with id {document_id}")
        document.appointment_id = appointment_id
        session.flush()
        log_audit(
            session,
            action,
            "PatientDocument",
            entity_id=document.id,
            details={"appointment_id": appointment_id, "document_type": document.document_type},
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(document)
        return document
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "PatientDocument",
            entity_id=document_id,
            details={"appointment_id": appointment_id, "reason": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise


def get_patient_documents(
    session: Session, patient_id: int, actor_user_id: int | None = None
) -> list[PatientDocument]:
    documents = (
        session.query(PatientDocument)
        .filter(PatientDocument.patient_id == patient_id)
        .order_by(PatientDocument.uploaded_at.desc())
        .all()
    )
    log_audit(
        session,
        "document.list",
        "PatientDocument",
        details={"patient_id": patient_id, "count": len(documents)},
        actor_user_id=actor_user_id,
    )
    session.commit()
    return documents