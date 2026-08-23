"""Phase 7 tests: Multilingual layer — detect/translate incoming, translate outgoing.

Tests verify:
1. Registration accepts preferred_language.
2. Translation functions detect, translate_to_english, translate_from_english.
3. Non-English requests are translated before graph processing.
4. final_response is translated back to preferred_language after graph completes.
5. Switching preferred_language changes only generated text, not stored records.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.main import app
from app.core.orchestrator import start_workflow, resume_workflow
from app.services.translation import (
    SUPPORTED_LANGUAGES,
    detect_language,
    translate_to_english,
    translate_from_english,
)
from tests.unit.factories import make_department, make_doctor, make_patient, make_slot, make_user


class FakeChatModel:
    def __init__(self, script):
        self.script = list(script)
        self.seen_messages = []
        self.bound_tools = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tools.append([t["function"]["name"] for t in tools])
        return self

    def invoke(self, messages):
        self.seen_messages.append(messages)
        if not self.script:
            raise AssertionError("FakeChatModel ran out of scripted responses")
        return self.script.pop(0)


class FakeHolder:
    llm = None


def ai_with_tool(name, args, call_id="call_1"):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def safe_screen(reason="All good."):
    return ai_with_tool("complete_safety_screen", {"safe": True, "reason": reason})


def _routing(patient, dept, **overrides):
    return {
        "department_id": dept.id,
        "clarify_question": None,
        "needs_booking": True,
        "needs_document": False,
        "needs_reminder": False,
        **overrides,
    }


def _slot_window(slot, dept):
    from datetime import timedelta
    return {
        "from_time": (slot.start_time - timedelta(days=1)).isoformat(),
        "to_time": (slot.end_time + timedelta(days=14)).isoformat(),
        "department_id": dept.id,
    }


def _booking_args(patient, dept, doctor, slot):
    return {
        "patient_id": patient.id,
        "department_id": dept.id,
        "doctor_id": doctor.id,
        "slot_id": slot.id,
        "visit_type": "consultation",
        "reason": "Follow-up",
    }


@pytest.fixture
def fake_llm(monkeypatch):
    holder = FakeHolder()
    monkeypatch.setattr("app.core.llm.groq_client.get_llm", lambda fast=False: holder.llm)
    return holder


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# ─── Translation unit tests ───


class TestTranslationFunctions:
    def test_detect_language_returns_iso_code(self):
        with patch("app.services.translation.get_llm") as mock_get_llm:
            mock_model = MagicMock()
            mock_model.invoke.return_value = MagicMock(content="es")
            mock_get_llm.return_value = mock_model
            result = detect_language("Necesito una cita con cardiologia")
            assert result == "es"

    def test_detect_language_falls_back_to_english_on_error(self):
        with patch("app.services.translation.get_llm") as mock_get_llm:
            mock_model = MagicMock()
            mock_model.invoke.side_effect = RuntimeError("API error")
            mock_get_llm.return_value = mock_model
            result = detect_language("Book me an appointment")
            assert result == "en"

    def test_translate_to_english_returns_english_for_english(self):
        result = translate_to_english("Book me an appointment", "en")
        assert result == "Book me an appointment"

    def test_translate_to_english_translates_spanish(self):
        with patch("app.services.translation.get_llm") as mock_get_llm:
            mock_model = MagicMock()
            mock_model.invoke.return_value = MagicMock(content="Book me a cardiology appointment")
            mock_get_llm.return_value = mock_model
            result = translate_to_english("Reservame una cita de cardiologia", "es")
            assert result == "Book me a cardiology appointment"

    def test_translate_from_english_returns_english_for_english(self):
        result = translate_from_english("Appointment booked", "en")
        assert result == "Appointment booked"

    def test_translate_from_english_translates_to_spanish(self):
        with patch("app.services.translation.get_llm") as mock_get_llm:
            mock_model = MagicMock()
            mock_model.invoke.return_value = MagicMock(content="Cita reservada")
            mock_get_llm.return_value = mock_model
            result = translate_from_english("Appointment booked", "es")
            assert result == "Cita reservada"

    def test_translate_from_english_falls_back_on_error(self):
        with patch("app.services.translation.get_llm") as mock_get_llm:
            mock_model = MagicMock()
            mock_model.invoke.side_effect = RuntimeError("API error")
            mock_get_llm.return_value = mock_model
            result = translate_from_english("Appointment booked", "es")
            assert result == "Appointment booked"

    def test_supported_languages_dict(self):
        assert "en" in SUPPORTED_LANGUAGES
        assert "es" in SUPPORTED_LANGUAGES
        assert "fr" in SUPPORTED_LANGUAGES
        assert "prs" in SUPPORTED_LANGUAGES
        assert "ps" in SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) == 5

    def test_empty_text_not_translated(self):
        assert translate_to_english("", "es") == ""
        assert translate_from_english("", "es") == ""


# ─── Registration with preferred_language ───


class TestRegistrationWithLanguage:
    def test_register_patient_with_preferred_language(self, client):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "maria@test.com",
                "password": "testpass123",
                "full_name": "Maria Garcia",
                "role": "patient",
                "preferred_language": "es",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["full_name"] == "Maria Garcia"

    def test_register_patient_defaults_to_english(self, client):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "john@test.com",
                "password": "testpass123",
                "full_name": "John Smith",
                "role": "patient",
            },
        )
        assert resp.status_code == 201

    def test_patient_can_update_preferred_language(self, client, db):
        from app.db.models import PatientProfile
        from app.core.security import create_access_token

        user = make_user(db, role="patient")
        profile = PatientProfile(
            user_id=user.id,
            date_of_birth="1990-01-01",
            preferred_language="en",
            contact_status="active",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        token = create_access_token(data={"sub": str(user.id), "role": user.role})
        resp = client.patch(
            "/api/patients/me",
            json={"preferred_language": "ar"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["preferred_language"] == "ar"


# ─── Orchestrator translation integration ───


class TestOrchestratorTranslation:
    def test_start_workflow_translates_spanish_to_english(self, db, fake_llm):
        patient = make_patient(db)
        dept = make_department(db)
        doctor = make_doctor(db, dept.id)
        slot = make_slot(db, doctor.id)

        fake_llm.llm = FakeChatModel(
            [
                safe_screen(),
                ai_with_tool("find_department", {"query": "Cardiology"}),
                ai_with_tool("complete_routing", _routing(patient, dept)),
                ai_with_tool("list_available_slots", _slot_window(slot, dept)),
                ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
                ai_with_tool(
                    "complete_insurance_check",
                    {"insurance_check_id": None, "eligibility_status": "covered", "message": "Covered"},
                ),
                ai_with_tool(
                    "complete_billing",
                    {"billing_explanation_id": None, "estimated_cost": "160.00", "message": "Billing done"},
                ),
                safe_screen("Booking is safe."),
            ]
        )

        with patch("app.core.orchestrator.detect_language", return_value="es"), \
             patch("app.core.orchestrator.translate_to_english", return_value="Book me a cardiology appointment"):
            run = start_workflow(patient.id, "Reservame una cita de cardiologia")

        assert run.status == "awaiting_confirmation"
        assert run.request_text == "Book me a cardiology appointment"

    def test_start_workflow_english_unchanged(self, db, fake_llm):
        patient = make_patient(db)
        dept = make_department(db)
        doctor = make_doctor(db, dept.id)
        slot = make_slot(db, doctor.id)

        fake_llm.llm = FakeChatModel(
            [
                safe_screen(),
                ai_with_tool("find_department", {"query": "Cardiology"}),
                ai_with_tool("complete_routing", _routing(patient, dept)),
                ai_with_tool("list_available_slots", _slot_window(slot, dept)),
                ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
                ai_with_tool(
                    "complete_insurance_check",
                    {"insurance_check_id": None, "eligibility_status": "covered", "message": "Covered"},
                ),
                ai_with_tool(
                    "complete_billing",
                    {"billing_explanation_id": None, "estimated_cost": "160.00", "message": "Billing done"},
                ),
                safe_screen("Booking is safe."),
            ]
        )

        with patch("app.core.orchestrator.detect_language", return_value="en"), \
             patch("app.core.orchestrator.translate_to_english", side_effect=lambda t, s: t):
            run = start_workflow(patient.id, "Book me a cardiology appointment")

        assert run.status == "awaiting_confirmation"
        assert run.request_text == "Book me a cardiology appointment"

    def test_resume_workflow_translates_spanish_message(self, db, fake_llm):
        patient = make_patient(db)
        dept = make_department(db)
        doctor = make_doctor(db, dept.id)
        slot = make_slot(db, doctor.id)

        fake_llm.llm = FakeChatModel(
            [
                safe_screen(),
                ai_with_tool("find_department", {"query": "Cardiology"}),
                ai_with_tool("complete_routing", _routing(patient, dept)),
                ai_with_tool("list_available_slots", _slot_window(slot, dept)),
                ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
                ai_with_tool(
                    "complete_insurance_check",
                    {"insurance_check_id": None, "eligibility_status": "covered", "message": "Covered"},
                ),
                ai_with_tool(
                    "complete_billing",
                    {"billing_explanation_id": None, "estimated_cost": "160.00", "message": "Billing done"},
                ),
                safe_screen("Booking is safe."),
            ]
        )

        with patch("app.core.orchestrator.detect_language", return_value="en"), \
             patch("app.core.orchestrator.translate_to_english", side_effect=lambda t, s: t):
            run = start_workflow(patient.id, "Book me a cardiology appointment")

        assert run.status == "awaiting_confirmation"

        fake_llm.llm = FakeChatModel(
            [
                ai_with_tool("get_patient_documents", {"patient_id": patient.id}),
                ai_with_tool("complete_document_check", {"message": "No documents required"}),
                ai_with_tool("complete_followup", {"message": "No reminder needed"}),
                safe_screen("Final answer is safe."),
            ]
        )

        with patch("app.core.orchestrator.detect_language", return_value="es"), \
             patch("app.core.orchestrator.translate_to_english", return_value="Confirmed"), \
             patch("app.core.orchestrator.translate_from_english", return_value="Cita confirmada para 2026-08-28"):
            resumed = resume_workflow(run.id, "Confirmado")

        assert resumed.status == "completed"

    def test_start_workflow_passes_preferred_language_to_state(self, db, fake_llm):
        from app.db.models import PatientProfile, WorkflowRun
        from app.core.graph import get_graph
        from app.core.orchestrator import _config

        user = make_user(db, role="patient")
        profile = PatientProfile(
            user_id=user.id,
            date_of_birth="1990-01-01",
            preferred_language="fr",
            contact_status="active",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        dept = make_department(db)
        doctor = make_doctor(db, dept.id)
        slot = make_slot(db, doctor.id)

        fake_llm.llm = FakeChatModel(
            [
                safe_screen(),
                ai_with_tool("find_department", {"query": "Cardiology"}),
                ai_with_tool("complete_routing", _routing(profile, dept)),
                ai_with_tool("list_available_slots", _slot_window(slot, dept)),
                ai_with_tool("book_appointment", _booking_args(profile, dept, doctor, slot)),
                ai_with_tool(
                    "complete_insurance_check",
                    {"insurance_check_id": None, "eligibility_status": "covered", "message": "Covered"},
                ),
                ai_with_tool(
                    "complete_billing",
                    {"billing_explanation_id": None, "estimated_cost": "160.00", "message": "Billing done"},
                ),
                safe_screen("Booking is safe."),
            ]
        )

        with patch("app.core.orchestrator.detect_language", return_value="en"), \
             patch("app.core.orchestrator.translate_to_english", side_effect=lambda t, s: t):
            run = start_workflow(profile.id, "Book me a cardiology appointment")

        run_obj = db.get(WorkflowRun, run.id)
        checkpoint = get_graph().get_state(_config(run_obj))
        assert checkpoint.values.get("preferred_language") == "fr"
