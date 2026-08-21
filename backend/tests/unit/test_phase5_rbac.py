"""Phase 5 tests: auth, RBAC, patient-scoped workflows.

Proves the three AGENT.md success criteria:
1. A patient JWT cannot read or modify another patient's records.
2. A patient JWT is rejected by staff-only routes at the API level.
3. Resolving an escalation is only possible as staff and records reviewed_by.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.models import (
    AppointmentSlot,
    Department,
    Doctor,
    Escalation,
    PatientProfile,
    User,
    WorkflowRun,
)
from app.main import app


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_user(
    db,
    email: str,
    role: str = "patient",
    password: str = "testpass123",
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=f"Test {role.title()}",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_patient_profile(db, user: User) -> PatientProfile:
    profile = PatientProfile(
        user_id=user.id,
        date_of_birth=date(1990, 1, 1),
        preferred_language="en",
        contact_status="active",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _token(user: User) -> str:
    return create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
        }
    )


def _client() -> TestClient:
    return TestClient(
        app,
        raise_server_exceptions=False,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def patient_a(db):
    user = _make_user(
        db,
        "patient_a@test.com",
        "patient",
    )
    profile = _make_patient_profile(db, user)
    return user, profile


@pytest.fixture
def patient_b(db):
    user = _make_user(
        db,
        "patient_b@test.com",
        "patient",
    )
    profile = _make_patient_profile(db, user)
    return user, profile


@pytest.fixture
def staff_user(db):
    return _make_user(
        db,
        "staff@test.com",
        "staff",
    )


@pytest.fixture
def client():
    return _client()


# ── Registration and Login ───────────────────────────────────────────────────


class TestAuth:
    def test_register_patient(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "newpatient@test.com",
                "password": "securepass123",
                "full_name": "New Patient",
                "role": "patient",
            },
        )

        assert resp.status_code == 201

        data = resp.json()

        assert data["email"] == "newpatient@test.com"
        assert data["role"] == "patient"
        assert "id" in data

        profile = (
            db.query(PatientProfile)
            .filter(PatientProfile.user_id == data["id"])
            .first()
        )

        assert profile is not None

    def test_register_staff(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "newstaff@test.com",
                "password": "securepass123",
                "full_name": "New Staff",
                "role": "staff",
            },
        )

        assert resp.status_code == 201
        assert resp.json()["role"] == "staff"

        profile = (
            db.query(PatientProfile)
            .filter(PatientProfile.user_id == resp.json()["id"])
            .first()
        )

        assert profile is None

    def test_register_duplicate_email(self, client, db):
        _make_user(
            db,
            "dup@test.com",
        )

        resp = client.post(
            "/api/auth/register",
            json={
                "email": "dup@test.com",
                "password": "securepass123",
                "full_name": "Dup",
                "role": "patient",
            },
        )

        assert resp.status_code == 409

    def test_login_success(self, client, db):
        _make_user(
            db,
            "login@test.com",
            password="mypass123",
        )

        resp = client.post(
            "/api/auth/login",
            json={
                "email": "login@test.com",
                "password": "mypass123",
            },
        )

        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert resp.json()["token_type"] == "bearer"

    def test_login_wrong_password(self, client, db):
        _make_user(
            db,
            "login2@test.com",
            password="mypass123",
        )

        resp = client.post(
            "/api/auth/login",
            json={
                "email": "login2@test.com",
                "password": "wrongpassword",
            },
        )

        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/auth/login",
            json={
                "email": "nobody@test.com",
                "password": "x",
            },
        )

        assert resp.status_code == 401


# ── AGENT.md Criterion 1: Patient cannot read/modify another patient's data ──


class TestPatientCannotAccessOtherPatientData:
    def test_patient_cannot_read_other_patient_profile(
        self,
        client,
        patient_a,
        patient_b,
    ):
        user_a, profile_a = patient_a
        user_b, profile_b = patient_b

        token_a = _token(user_a)

        from app.db.session import SessionLocal

        session = SessionLocal()

        try:
            run = WorkflowRun(
                patient_id=profile_b.id,
                request_text="Test request from B",
                status="completed",
                thread_id="test-thread-b",
            )

            session.add(run)
            session.commit()
            session.refresh(run)

            run_id = run.id

        finally:
            session.close()

        resp = client.get(
            f"/api/workflows/{run_id}",
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403

    def test_patient_cannot_resume_other_patient_workflow(
        self,
        client,
        patient_a,
        patient_b,
    ):
        user_a, profile_a = patient_a
        user_b, profile_b = patient_b

        token_a = _token(user_a)

        from app.db.session import SessionLocal

        session = SessionLocal()

        try:
            run = WorkflowRun(
                patient_id=profile_b.id,
                request_text="Test request from B",
                status="awaiting_confirmation",
                thread_id="test-thread-b2",
            )

            session.add(run)
            session.commit()
            session.refresh(run)

            run_id = run.id

        finally:
            session.close()

        resp = client.post(
            f"/api/workflows/{run_id}/resume",
            json={
                "message": "Trying to hijack B's workflow",
            },
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403

    def test_patient_cannot_create_workflow_for_other_patient(
        self,
        client,
        db,
        patient_a,
        patient_b,
        monkeypatch,
    ):
        """Patient-submitted patient_id must be ignored.

        Patient A deliberately submits Patient B's patient_id.

        The API must:
        1. Authenticate Patient A.
        2. Resolve Patient A's PatientProfile.
        3. Ignore the patient_id supplied in the request body.
        4. Create the workflow for Patient A.
        """

        user_a, profile_a = patient_a
        user_b, profile_b = patient_b

        token_a = _token(user_a)

        captured = {}

        def fake_start_workflow(
            patient_id,
            request_text,
            document_id=None,
        ):
            """Create a real DB row so response-model validation succeeds."""

            captured["patient_id"] = patient_id
            captured["request_text"] = request_text
            captured["document_id"] = document_id

            run = WorkflowRun(
                patient_id=patient_id,
                request_text=request_text,
                status="completed",
                thread_id="test-rbac-thread",
            )

            db.add(run)
            db.commit()
            db.refresh(run)

            return run

        # workflows.py imports start_workflow directly:
        #
        #     from app.core.orchestrator import start_workflow
        #
        # Therefore patch the symbol where it is USED.
        monkeypatch.setattr(
            "app.api.workflows.start_workflow",
            fake_start_workflow,
        )

        # Patient A submits Patient B's ID.
        resp = client.post(
            "/api/workflows/run",
            json={
                "patient_id": profile_b.id,
                "request_text": "Book appointment for B",
            },
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 201

        data = resp.json()

        # The most important security assertion:
        # Patient A's authenticated identity wins over the
        # patient_id supplied by the client.
        assert captured["patient_id"] == profile_a.id

        assert data["patient_id"] == profile_a.id

        # Make sure Patient B was NOT used.
        assert captured["patient_id"] != profile_b.id

        assert data["request_text"] == "Book appointment for B"

    def test_patient_can_read_own_workflow(
        self,
        client,
        patient_a,
    ):
        user_a, profile_a = patient_a
        token_a = _token(user_a)

        from app.db.session import SessionLocal

        session = SessionLocal()

        try:
            run = WorkflowRun(
                patient_id=profile_a.id,
                request_text="My own request",
                status="completed",
                thread_id="test-thread-a",
            )

            session.add(run)
            session.commit()
            session.refresh(run)

            run_id = run.id

        finally:
            session.close()

        resp = client.get(
            f"/api/workflows/{run_id}",
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["patient_id"] == profile_a.id


# ── AGENT.md Criterion 2: Patient rejected by staff-only routes ──────────────


class TestPatientRejectedByStaffRoutes:
    def test_patient_cannot_list_departments(
        self,
        client,
        patient_a,
    ):
        user_a, _ = patient_a
        token_a = _token(user_a)

        resp = client.get(
            "/api/staff/departments",
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403
        assert "Staff access required" in resp.json()["detail"]

    def test_patient_cannot_create_department(
        self,
        client,
        patient_a,
    ):
        user_a, _ = patient_a
        token_a = _token(user_a)

        resp = client.post(
            "/api/staff/departments",
            json={
                "name": "Hacked Dept",
                "code": "HACK",
            },
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403

    def test_patient_cannot_list_doctors(
        self,
        client,
        patient_a,
    ):
        user_a, _ = patient_a
        token_a = _token(user_a)

        resp = client.get(
            "/api/staff/doctors",
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403

    def test_patient_cannot_create_doctor(
        self,
        client,
        patient_a,
        db,
    ):
        user_a, _ = patient_a
        token_a = _token(user_a)

        dept = Department(
            name="Cardiology",
            code="CARD",
        )

        db.add(dept)
        db.commit()
        db.refresh(dept)

        resp = client.post(
            "/api/staff/doctors",
            json={
                "department_id": dept.id,
                "name": "Dr. Hack",
                "specialty": "Hacking",
                "license_number": "FAKE123",
            },
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403

    def test_patient_cannot_list_escalations(
        self,
        client,
        patient_a,
    ):
        user_a, _ = patient_a
        token_a = _token(user_a)

        resp = client.get(
            "/api/escalations/",
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403

    def test_patient_cannot_resolve_escalation(
        self,
        client,
        patient_a,
        db,
    ):
        user_a, _ = patient_a
        token_a = _token(user_a)

        esc = Escalation(
            reason="Test escalation",
            severity="high",
            status="open",
        )

        db.add(esc)
        db.commit()
        db.refresh(esc)

        resp = client.post(
            f"/api/escalations/{esc.id}/resolve",
            json={
                "resolution_notes": "Trying to resolve as patient",
            },
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403

    def test_patient_cannot_list_slots(
        self,
        client,
        patient_a,
    ):
        user_a, _ = patient_a
        token_a = _token(user_a)

        resp = client.get(
            "/api/staff/slots",
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 403


# ── AGENT.md Criterion 3: Escalation resolution only as staff ────────────────


class TestEscalationResolutionStaffOnly:
    def test_staff_can_list_escalations(
        self,
        client,
        staff_user,
        db,
    ):
        token = _token(staff_user)

        esc = Escalation(
            reason="Needs review",
            severity="medium",
            status="open",
        )

        db.add(esc)
        db.commit()

        resp = client.get(
            "/api/escalations/",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_staff_can_resolve_escalation(
        self,
        client,
        staff_user,
        db,
    ):
        token = _token(staff_user)

        esc = Escalation(
            reason="Critical issue",
            severity="critical",
            status="open",
        )

        db.add(esc)
        db.commit()
        db.refresh(esc)

        resp = client.post(
            f"/api/escalations/{esc.id}/resolve",
            json={
                "resolution_notes": "Reviewed and handled by Dr. Smith",
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 200

        data = resp.json()

        assert data["status"] == "resolved"
        assert data["reviewed_by"] == staff_user.id
        assert data["resolution_notes"] == "Reviewed and handled by Dr. Smith"

    def test_cannot_resolve_already_resolved_escalation(
        self,
        client,
        staff_user,
        db,
    ):
        token = _token(staff_user)

        esc = Escalation(
            reason="Already done",
            severity="low",
            status="resolved",
            reviewed_by=staff_user.id,
        )

        db.add(esc)
        db.commit()
        db.refresh(esc)

        resp = client.post(
            f"/api/escalations/{esc.id}/resolve",
            json={
                "resolution_notes": "Trying again",
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 400

    def test_escalation_resolved_by_records_staff_user_id(
        self,
        client,
        staff_user,
        db,
    ):
        token = _token(staff_user)

        esc = Escalation(
            reason="Audit me",
            severity="high",
            status="open",
        )

        db.add(esc)
        db.commit()
        db.refresh(esc)

        resp = client.post(
            f"/api/escalations/{esc.id}/resolve",
            json={
                "resolution_notes": "Audited",
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 200

        from app.db.session import SessionLocal

        session = SessionLocal()

        try:
            refreshed = session.get(
                Escalation,
                esc.id,
            )

            assert refreshed is not None
            assert refreshed.reviewed_by == staff_user.id

        finally:
            session.close()


# ── Staff CRUD works correctly ───────────────────────────────────────────────


class TestStaffCRUD:
    def test_staff_can_create_department(
        self,
        client,
        staff_user,
    ):
        token = _token(staff_user)

        resp = client.post(
            "/api/staff/departments",
            json={
                "name": "Neurology",
                "code": "NEURO",
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 201
        assert resp.json()["name"] == "Neurology"

    def test_staff_can_create_and_list_doctors(
        self,
        client,
        staff_user,
        db,
    ):
        token = _token(staff_user)

        dept = Department(
            name="Onco",
            code="ONC",
        )

        db.add(dept)
        db.commit()
        db.refresh(dept)

        resp = client.post(
            "/api/staff/doctors",
            json={
                "department_id": dept.id,
                "name": "Dr. Oncology",
                "specialty": "Oncology",
                "license_number": "ONC-001",
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 201

        resp = client.get(
            "/api/staff/doctors",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 200

        assert any(
            doctor["name"] == "Dr. Oncology"
            for doctor in resp.json()
        )

    def test_staff_can_create_slot(
        self,
        client,
        staff_user,
        db,
    ):
        token = _token(staff_user)

        dept = Department(
            name="Cardio2",
            code="CA2",
        )

        db.add(dept)
        db.commit()
        db.refresh(dept)

        doctor = Doctor(
            department_id=dept.id,
            name="Dr. Slot",
            specialty="Cardiology",
            license_number="SLOT-001",
        )

        db.add(doctor)
        db.commit()
        db.refresh(doctor)

        start = (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).replace(
            hour=10,
            minute=0,
            second=0,
            microsecond=0,
        )

        resp = client.post(
            "/api/staff/slots",
            json={
                "doctor_id": doctor.id,
                "start_time": start.isoformat(),
                "end_time": (
                    start + timedelta(hours=1)
                ).isoformat(),
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 201

    def test_unauthenticated_rejected(
        self,
        client,
    ):
        resp = client.get(
            "/api/staff/departments",
        )

        assert resp.status_code == 401


# ── Patient profile routes ───────────────────────────────────────────────────


class TestPatientProfile:
    def test_patient_can_read_own_profile(
        self,
        client,
        patient_a,
    ):
        user_a, profile_a = patient_a
        token_a = _token(user_a)

        resp = client.get(
            "/api/patients/me",
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == profile_a.id

    def test_patient_can_update_own_profile(
        self,
        client,
        patient_a,
    ):
        user_a, profile_a = patient_a
        token_a = _token(user_a)

        resp = client.patch(
            "/api/patients/me",
            json={
                "phone": "+1-555-0199",
            },
            headers={
                "Authorization": f"Bearer {token_a}",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["phone"] == "+1-555-0199"

    def test_staff_cannot_use_patient_profile_route(
        self,
        client,
        staff_user,
    ):
        token = _token(staff_user)

        resp = client.get(
            "/api/patients/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 403


# ── Workflow routes with auth ────────────────────────────────────────────────


class TestWorkflowAuth:
    def test_unauthenticated_rejected(
        self,
        client,
    ):
        resp = client.post(
            "/api/workflows/run",
            json={
                "patient_id": 1,
                "request_text": "Help me",
            },
        )

        assert resp.status_code == 401

    def test_staff_can_see_any_workflow(
        self,
        client,
        staff_user,
        db,
    ):
        token = _token(staff_user)

        patient_user = _make_user(
            db,
            "any_patient@test.com",
            "patient",
        )

        patient_profile = _make_patient_profile(
            db,
            patient_user,
        )

        run = WorkflowRun(
            patient_id=patient_profile.id,
            request_text="Staff view test",
            status="completed",
            thread_id="staff-view-thread",
        )

        db.add(run)
        db.commit()
        db.refresh(run)

        resp = client.get(
            f"/api/workflows/{run.id}",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert resp.status_code == 200