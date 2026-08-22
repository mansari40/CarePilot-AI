"""Phase 8: Analytics dashboard tests."""

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Appointment,
    Department,
    Doctor,
    Escalation,
    InsuranceEligibilityCheck,
    InsurancePolicy,
    PatientDocument,
    PatientProfile,
    User,
)
from app.core.security import hash_password, create_access_token
from app.main import app

client = TestClient(app)


def _setup_deps(db: Session) -> Department:
    dept = Department(name="Cardiology", code="CARD", is_active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def _create_staff(db: Session) -> str:
    user = User(
        email=f"staff_analytics_{id(db)}@test.com",
        hashed_password=hash_password("test"),
        full_name="Analytics Staff",
        role="staff",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_access_token(data={"sub": str(user.id), "role": "staff"})


def _create_patient(db: Session, name: str = "Test Patient") -> PatientProfile:
    user = User(
        email=f"patient_{name.lower().replace(' ', '_')}_{id(db)}@test.com",
        hashed_password=hash_password("test"),
        full_name=name,
        role="patient",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    profile = PatientProfile(user_id=user.id, date_of_birth=date(1990, 1, 1))
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


# -- Analytics service unit tests --


def test_appointments_by_department(db: Session):
    from app.services.analytics_service import appointments_by_department

    dept = _setup_deps(db)
    patient = _create_patient(db, "Dept Test")
    appt = Appointment(patient_id=patient.id, department_id=dept.id, status="booked")
    db.add(appt)
    db.commit()

    result = appointments_by_department(db)
    assert isinstance(result, list)
    assert any(r["department"] == dept.name and r["count"] > 0 for r in result)


def test_appointments_by_status(db: Session):
    from app.services.analytics_service import appointments_by_status

    dept = _setup_deps(db)
    patient = _create_patient(db, "Status Test")
    for status in ["booked", "confirmed", "requested"]:
        appt = Appointment(patient_id=patient.id, department_id=dept.id, status=status)
        db.add(appt)
    db.commit()

    result = appointments_by_status(db)
    assert isinstance(result, list)
    statuses = {r["status"] for r in result}
    assert "booked" in statuses
    assert "confirmed" in statuses


def test_document_completion_rate(db: Session):
    from app.services.analytics_service import document_completion_rate

    dept = _setup_deps(db)
    patient = _create_patient(db, "Doc Test")
    appt1 = Appointment(patient_id=patient.id, department_id=dept.id, status="booked")
    appt2 = Appointment(patient_id=patient.id, department_id=dept.id, status="booked")
    db.add_all([appt1, appt2])
    db.commit()
    db.refresh(appt1)
    db.refresh(appt2)

    doc = PatientDocument(
        patient_id=patient.id,
        appointment_id=appt1.id,
        filename="test.pdf",
        storage_path="/tmp/test.pdf",
        document_type="referral",
        checksum="abc123",
    )
    db.add(doc)
    db.commit()

    result = document_completion_rate(db)
    assert result["total_appointments"] >= 2
    assert result["appointments_with_documents"] >= 1
    assert 0 <= result["completion_rate_pct"] <= 100


def test_escalation_stats_empty(db: Session):
    from app.services.analytics_service import escalation_stats

    result = escalation_stats(db)
    assert result["total"] == 0
    assert result["open"] == 0
    assert result["resolved"] == 0
    assert result["avg_resolution_seconds"] == 0.0
    assert result["by_severity"] == []


def test_escalation_stats_with_data(db: Session):
    from app.services.analytics_service import escalation_stats

    patient = _create_patient(db, "Esc Test")
    now = datetime.now(timezone.utc)
    esc = Escalation(
        patient_id=patient.id,
        severity="high",
        reason="chest pain",
        status="resolved",
        created_at=now - timedelta(hours=2),
        resolved_at=now,
    )
    db.add(esc)
    db.commit()

    result = escalation_stats(db)
    assert result["total"] >= 1
    assert result["resolved"] >= 1
    assert result["avg_resolution_seconds"] > 0


def test_insurance_eligibility_outcomes(db: Session):
    from app.services.analytics_service import insurance_eligibility_outcomes

    result = insurance_eligibility_outcomes(db)
    assert isinstance(result, list)


def test_busiest_doctors(db: Session):
    from app.services.analytics_service import busiest_doctors

    result = busiest_doctors(db, limit=3)
    assert isinstance(result, list)
    assert len(result) <= 3


def test_busiest_days_empty(db: Session):
    from app.services.analytics_service import busiest_slots

    result = busiest_slots(db)
    assert isinstance(result, list)
    assert result == []


def test_get_dashboard_returns_all_keys(db: Session):
    from app.services.analytics_service import get_dashboard

    result = get_dashboard(db)
    expected_keys = {
        "appointments_by_department",
        "appointments_by_status",
        "avg_request_to_booking",
        "document_completion",
        "escalation_stats",
        "insurance_eligibility_outcomes",
        "busiest_doctors",
        "busiest_days",
    }
    assert expected_keys == set(result.keys())


# -- API endpoint tests --


def test_dashboard_requires_staff_auth(db: Session):
    resp = client.get("/api/analytics/dashboard")
    assert resp.status_code == 401


def test_dashboard_rejects_patient(db: Session):
    patient = _create_patient(db, "No Staff")
    token = create_access_token(data={"sub": str(patient.user_id), "role": "patient"})
    resp = client.get("/api/analytics/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_dashboard_returns_200_for_staff(db: Session):
    token = _create_staff(db)
    resp = client.get("/api/analytics/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    for key in [
        "appointments_by_department",
        "appointments_by_status",
        "avg_request_to_booking",
        "document_completion",
        "escalation_stats",
        "insurance_eligibility_outcomes",
        "busiest_doctors",
        "busiest_days",
    ]:
        assert key in data


def test_dashboard_handles_zero_records(db: Session):
    token = _create_staff(db)
    resp = client.get("/api/analytics/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["escalation_stats"]["total"] == 0
    assert data["escalation_stats"]["by_severity"] == []
    assert data["document_completion"]["total_appointments"] >= 0
    assert isinstance(data["document_completion"]["completion_rate_pct"], float)
    assert data["busiest_days"] == []
    assert data["appointments_by_department"] == []
    assert data["appointments_by_status"] == []
