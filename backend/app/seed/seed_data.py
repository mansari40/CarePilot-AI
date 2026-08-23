"""Populate the AgentCare database with realistic synthetic data.

All data is fictional. Run with:  python -m app.seed.seed_data
The script is idempotent: it truncates every table first, then inserts.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_password
from app.db.models import (
    Appointment,
    AppointmentSlot,
    AuditEvent,
    BillingExplanation,
    BillingLineItem,
    Department,
    Doctor,
    Escalation,
    FeeScheduleItem,
    InsuranceEligibilityCheck,
    InsurancePolicy,
    PatientDocument,
    PatientProfile,
    Reminder,
    User,
    WorkflowRun,
)
from app.db.session import Base, SessionLocal

NOW = datetime.now(timezone.utc)


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def truncate_all(session: Session) -> None:
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    session.commit()


def seed(session: Session) -> None:
    truncate_all(session)

    # ── Users ────────────────────────────────────────────────────────────
    staff_mitchell = User(
        email="sarah.mitchell@carepilot.test",
        hashed_password="(synthetic-staff-pw)",
        full_name="Dr. Sarah Mitchell",
        role="staff",
    )
    staff_rodriguez = User(
        email="tom.rodriguez@carepilot.test",
        hashed_password="(synthetic-staff-pw)",
        full_name="Tom Rodriguez",
        role="staff",
    )
    staff_admin = User(
        email="admin@carepilot.com",
        hashed_password=hash_password("abcdef123456!"),
        full_name="Admin User",
        role="staff",
    )
    patients = [
        User(email="aisha.khan@example.test", hashed_password="(synthetic-pw)", full_name="Aisha Khan", role="patient"),
        User(email="carlos.mendoza@example.test", hashed_password="(synthetic-pw)", full_name="Carlos Mendoza", role="patient"),
        User(email="marie.dubois@example.test", hashed_password="(synthetic-pw)", full_name="Marie Dubois", role="patient"),
        User(email="fatima.alarashid@example.test", hashed_password="(synthetic-pw)", full_name="Fatima Al-Rashid", role="patient"),
        User(email="priya.sharma@example.test", hashed_password="(synthetic-pw)", full_name="Priya Sharma", role="patient"),
        User(email="ahmed.hussain@example.test", hashed_password="(synthetic-pw)", full_name="Ahmed Hussain", role="patient"),
        User(email="john.carter@example.test", hashed_password="(synthetic-pw)", full_name="John Carter", role="patient"),
        User(email="elena.petrova@example.test", hashed_password="(synthetic-pw)", full_name="Elena Petrova", role="patient"),
    ]
    session.add_all([staff_mitchell, staff_rodriguez, staff_admin, *patients])
    session.flush()

    # ── Patient profiles (contact statuses: new / contacted / active) ─────
    profiles = [
        PatientProfile(user_id=patients[0].id, date_of_birth=date(1986, 3, 14), gender="female", phone="+1 555 010 2201", preferred_language="en", contact_status="active", emergency_contact_name="Omar Khan", emergency_contact_phone="+1 555 010 2202"),
        PatientProfile(user_id=patients[1].id, date_of_birth=date(1978, 11, 2), gender="male", phone="+1 555 010 3301", preferred_language="es", contact_status="active", emergency_contact_name="Lucia Mendoza", emergency_contact_phone="+1 555 010 3302"),
        PatientProfile(user_id=patients[2].id, date_of_birth=date(1992, 7, 21), gender="female", phone="+1 555 010 4401", preferred_language="fr", contact_status="contacted", emergency_contact_name="Paul Dubois", emergency_contact_phone="+1 555 010 4402"),
        PatientProfile(user_id=patients[3].id, date_of_birth=date(1959, 1, 30), gender="female", phone="+1 555 010 5501", preferred_language="en", contact_status="contacted", emergency_contact_name="Hassan Al-Rashid", emergency_contact_phone="+1 555 010 5502"),
        PatientProfile(user_id=patients[4].id, date_of_birth=date(2001, 9, 8), gender="female", phone="+1 555 010 6601", preferred_language="es", contact_status="active", emergency_contact_name="Ravi Sharma", emergency_contact_phone="+1 555 010 6602"),
        PatientProfile(user_id=patients[5].id, date_of_birth=date(1989, 5, 17), gender="male", phone="+1 555 010 7701", preferred_language="fr", contact_status="new", emergency_contact_name="Zainab Hussain", emergency_contact_phone="+1 555 010 7702"),
        PatientProfile(user_id=patients[6].id, date_of_birth=date(1971, 12, 5), gender="male", phone="+1 555 010 8801", preferred_language="en", contact_status="new", emergency_contact_name="Anna Carter", emergency_contact_phone="+1 555 010 8802"),
        PatientProfile(user_id=patients[7].id, date_of_birth=date(1995, 4, 25), gender="female", phone="+1 555 010 9901", preferred_language="en", contact_status="active", emergency_contact_name="Dmitri Petrova", emergency_contact_phone="+1 555 010 9902"),
    ]
    session.add_all(profiles)
    session.flush()

    # ── Departments ───────────────────────────────────────────────────────
    departments = [
        Department(name="Cardiology", code="CARD", description="Heart and cardiovascular care", building="West Wing", floor="3"),
        Department(name="Neurology", code="NEUR", description="Brain, spine and nervous system", building="West Wing", floor="2"),
        Department(name="Orthopedics", code="ORTH", description="Bones, joints and musculoskeletal", building="East Wing", floor="1"),
        Department(name="Pediatrics", code="PEDI", description="Child and adolescent care", building="East Wing", floor="2"),
        Department(name="General Medicine", code="GENE", description="Primary and general internal medicine", building="Main Building", floor="1"),
        Department(name="Dermatology", code="DERM", description="Skin, hair and nail conditions", building="Main Building", floor="2"),
        Department(name="Radiology", code="RADI", description="Imaging and diagnostic radiology", building="West Wing", floor="B1"),
    ]
    session.add_all(departments)
    session.flush()

    # ── Doctors (2 per department) ────────────────────────────────────────
    doctors = [
        Doctor(department_id=departments[0].id, name="Dr. Elena Vasquez", specialty="Interventional Cardiology", license_number="LIC-CARD-101", email="e.vasquez@carepilot.test"),
        Doctor(department_id=departments[0].id, name="Dr. Robert Chen", specialty="Cardiology", license_number="LIC-CARD-102", email="r.chen@carepilot.test"),
        Doctor(department_id=departments[1].id, name="Dr. Priya Natarajan", specialty="Neurology", license_number="LIC-NEUR-201", email="p.natarajan@carepilot.test"),
        Doctor(department_id=departments[1].id, name="Dr. James O'Brien", specialty="Epilepsy and Seizure Disorders", license_number="LIC-NEUR-202", email="j.obrien@carepilot.test"),
        Doctor(department_id=departments[2].id, name="Dr. Michael Brooks", specialty="Orthopedic Surgery", license_number="LIC-ORTH-301", email="m.brooks@carepilot.test"),
        Doctor(department_id=departments[2].id, name="Dr. Linda Park", specialty="Sports Medicine", license_number="LIC-ORTH-302", email="l.park@carepilot.test"),
        Doctor(department_id=departments[3].id, name="Dr. Amira Hassan", specialty="Pediatrics", license_number="LIC-PEDI-401", email="a.hassan@carepilot.test"),
        Doctor(department_id=departments[3].id, name="Dr. Daniel Kim", specialty="Pediatric Gastroenterology", license_number="LIC-PEDI-402", email="d.kim@carepilot.test"),
        Doctor(department_id=departments[4].id, name="Dr. Sarah Mitchell", specialty="Internal Medicine", license_number="LIC-GENE-501", email="s.mitchell@carepilot.test"),
        Doctor(department_id=departments[4].id, name="Dr. William Torres", specialty="General Practice", license_number="LIC-GENE-502", email="w.torres@carepilot.test"),
        Doctor(department_id=departments[5].id, name="Dr. Grace Liu", specialty="Dermatology", license_number="LIC-DERM-601", email="g.liu@carepilot.test"),
        Doctor(department_id=departments[5].id, name="Dr. Omar Farouk", specialty="Dermatology and Dermatologic Surgery", license_number="LIC-DERM-602", email="o.farouk@carepilot.test"),
        Doctor(department_id=departments[6].id, name="Dr. Hannah Weiss", specialty="Diagnostic Radiology", license_number="LIC-RADI-701", email="h.weiss@carepilot.test"),
        Doctor(department_id=departments[6].id, name="Dr. Peter Novak", specialty="Interventional Radiology", license_number="LIC-RADI-702", email="p.novak@carepilot.test"),
    ]
    session.add_all(doctors)
    session.flush()

    # ── Slots: next 5 weekdays, 4 per doctor per day; a handful pre-booked ─
    slots: list[AppointmentSlot] = []
    start_of_week = NOW.date() + timedelta(days=1)
    while start_of_week.weekday() >= 5:
        start_of_week += timedelta(days=1)
    times = [9, 10, 13, 15]
    for day_offset in range(5):
        day = start_of_week + timedelta(days=day_offset)
        for doctor in doctors:
            for hour in times:
                slots.append(
                    AppointmentSlot(
                        doctor_id=doctor.id,
                        start_time=datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc),
                        end_time=datetime(day.year, day.month, day.day, hour + 1, tzinfo=timezone.utc),
                    )
                )
    session.add_all(slots)
    session.flush()

    # ── Appointments: mix of stages ──────────────────────────────────────
    def slot_for(doctor_idx: int, day_offset: int, time_idx: int) -> AppointmentSlot:
        return slots[day_offset * len(doctors) * len(times) + doctor_idx * len(times) + time_idx]

    booked_slots = {
        "aisha": slot_for(0, 0, 1),
        "carlos": slot_for(4, 1, 0),
        "fatima": slot_for(1, 2, 2),
        "ahmed": slot_for(2, 0, 3),
        "john": slot_for(8, 3, 1),
    }
    for slot in booked_slots.values():
        slot.is_booked = True

    appt_aisha = Appointment(
        patient_id=profiles[0].id, department_id=departments[0].id, doctor_id=doctors[0].id,
        slot_id=booked_slots["aisha"].id, status="confirmed", visit_type="follow_up",
        reason="Cardiology follow-up after recent ECG. Patient reports feeling well; follow-up requested by cardiology.",
        scheduled_for=booked_slots["aisha"].start_time, notes="Bring previous ECG for comparison.",
    )
    appt_aisha_done = Appointment(
        patient_id=profiles[0].id, department_id=departments[0].id, doctor_id=doctors[1].id,
        status="completed", visit_type="follow_up",
        reason="Post-procedure cardiology follow-up.", scheduled_for=NOW - timedelta(days=12),
    )
    appt_carlos = Appointment(
        patient_id=profiles[1].id, department_id=departments[2].id, doctor_id=doctors[4].id,
        slot_id=booked_slots["carlos"].id, status="scheduled", visit_type="consultation",
        reason="Knee pain during sport; consult orthopedic surgeon.", scheduled_for=booked_slots["carlos"].start_time,
    )
    appt_marie = Appointment(
        patient_id=profiles[2].id, department_id=departments[5].id, doctor_id=doctors[10].id,
        status="requested", visit_type="consultation", reason="Persistent skin rash on forearm.",
    )
    appt_fatima = Appointment(
        patient_id=profiles[3].id, department_id=departments[0].id, doctor_id=doctors[1].id,
        slot_id=booked_slots["fatima"].id, status="confirmed", visit_type="checkup",
        reason="Annual cardiac checkup with blood pressure review.", scheduled_for=booked_slots["fatima"].start_time,
    )
    appt_priya_done = Appointment(
        patient_id=profiles[4].id, department_id=departments[4].id, doctor_id=doctors[9].id,
        status="completed", visit_type="consultation", reason="General health review.", scheduled_for=NOW - timedelta(days=30),
    )
    appt_priya_cancel = Appointment(
        patient_id=profiles[4].id, department_id=departments[3].id, doctor_id=doctors[7].id,
        status="cancelled", visit_type="consultation", reason="School referral for pediatric consult.", scheduled_for=NOW - timedelta(days=5),
    )
    appt_ahmed = Appointment(
        patient_id=profiles[5].id, department_id=departments[1].id, doctor_id=doctors[2].id,
        slot_id=booked_slots["ahmed"].id, status="scheduled", visit_type="consultation",
        reason="New patient neurology consult for recurring headaches.", scheduled_for=booked_slots["ahmed"].start_time,
    )
    appt_elena = Appointment(
        patient_id=profiles[7].id, department_id=departments[6].id, doctor_id=doctors[13].id,
        status="requested", visit_type="procedure", reason="Radiology imaging requested by orthopedics.",
    )
    appt_john = Appointment(
        patient_id=profiles[6].id, department_id=departments[4].id, doctor_id=doctors[8].id,
        slot_id=booked_slots["john"].id, status="confirmed", visit_type="new_patient",
        reason="New patient general medicine consult.", scheduled_for=booked_slots["john"].start_time,
    )

    appointments = [appt_aisha, appt_aisha_done, appt_carlos, appt_marie, appt_fatima, appt_priya_done, appt_priya_cancel, appt_ahmed, appt_elena, appt_john]
    session.add_all(appointments)
    session.flush()

    # ── Documents (including one explicit duplicate pair) ────────────────
    documents = [
        PatientDocument(patient_id=profiles[0].id, appointment_id=appt_aisha.id, filename="ecg_report_2026_08.pdf", storage_path="/uploads/aisha/ecg_report_2026_08.pdf", document_type="ecg", checksum=_checksum("aisha-ecg-1")),
        PatientDocument(patient_id=profiles[0].id, appointment_id=appt_aisha_done.id, filename="lab_blood_panel.pdf", storage_path="/uploads/aisha/lab_blood_panel.pdf", document_type="lab_report", checksum=_checksum("aisha-lab-1")),
        PatientDocument(patient_id=profiles[1].id, appointment_id=appt_carlos.id, filename="ortho_referral.pdf", storage_path="/uploads/carlos/ortho_referral.pdf", document_type="referral", checksum=_checksum("carlos-ref-1")),
        PatientDocument(patient_id=profiles[2].id, appointment_id=appt_marie.id, filename="lab_allergy_panel.pdf", storage_path="/uploads/marie/lab_allergy_panel.pdf", document_type="lab_report", checksum=_checksum("marie-lab-1")),
        PatientDocument(patient_id=profiles[2].id, appointment_id=appt_marie.id, filename="lab_allergy_panel_copy.pdf", storage_path="/uploads/marie/lab_allergy_panel_copy.pdf", document_type="lab_report", checksum=_checksum("marie-lab-1"), is_duplicate=True),
        PatientDocument(patient_id=profiles[4].id, appointment_id=appt_priya_done.id, filename="prescription_vitamins.pdf", storage_path="/uploads/priya/prescription_vitamins.pdf", document_type="prescription", checksum=_checksum("priya-rx-1")),
        PatientDocument(patient_id=profiles[7].id, appointment_id=appt_elena.id, filename="mri_request_form.pdf", storage_path="/uploads/elena/mri_request_form.pdf", document_type="referral", checksum=_checksum("elena-ref-1")),
    ]
    session.add_all(documents)

    # ── Workflow runs ────────────────────────────────────────────────────
    workflows = [
        WorkflowRun(patient_id=profiles[0].id, request_text="I had an ECG last week and would like a cardiology follow-up appointment, my ECG report is attached.", intent="book_appointment", status="completed", current_step="follow_up_scheduled", thread_id="3f2a9c1e-0001-4a6b-9f10-cafebabe0001", state={"route": "cardiology", "appointment_id": appt_aisha.id, "documents": ["ecg_report_2026_08.pdf"], "insurance": "covered", "billing": "generated"}),
        WorkflowRun(patient_id=profiles[5].id, request_text="I keep having strong headaches and I need to see a neurologist.", intent="book_appointment", status="running", current_step="appointment_booking", thread_id="3f2a9c1e-0002-4a6b-9f10-cafebabe0002", state={"route": "neurology", "appointment_id": appt_ahmed.id}),
        WorkflowRun(patient_id=profiles[2].id, request_text="I have a rash on my arm and would like a dermatology appointment.", intent="book_appointment", status="needs_document", current_step="document_coordination", thread_id="3f2a9c1e-0003-4a6b-9f10-cafebabe0003", state={"route": "dermatology", "appointment_id": appt_marie.id, "missing_documents": ["referral"]}),
        WorkflowRun(patient_id=profiles[6].id, request_text="Please book me a general checkup, I am a new patient.", intent="book_appointment", status="pending", current_step=None, thread_id=None, state={}),
        WorkflowRun(patient_id=profiles[3].id, request_text="My chest hurts right now, is this a heart attack? I need someone to tell me what to do immediately.", intent="emergency", status="escalated", current_step="safety_screen", thread_id="3f2a9c1e-0004-4a6b-9f10-cafebabe0004", state={"route": "escalate", "reason": "emergency language detected"}),
    ]
    session.add_all(workflows)
    session.flush()

    # ── Reminders ────────────────────────────────────────────────────────
    reminders = [
        Reminder(appointment_id=appt_aisha.id, patient_id=profiles[0].id, reminder_type="appointment", scheduled_for=appt_aisha.scheduled_for - timedelta(hours=24), channel="in_app", message="Reminder: Cardiology follow-up tomorrow with Dr. Vasquez.", status="pending"),
        Reminder(appointment_id=appt_carlos.id, patient_id=profiles[1].id, reminder_type="appointment", scheduled_for=appt_carlos.scheduled_for - timedelta(hours=24), channel="in_app", message="Reminder: Orthopedics consultation with Dr. Brooks.", status="pending"),
        Reminder(appointment_id=appt_priya_done.id, patient_id=profiles[4].id, reminder_type="follow_up", scheduled_for=NOW + timedelta(days=14), channel="in_app", message="Follow-up: schedule a general health review within 2 weeks.", status="pending"),
        Reminder(appointment_id=appt_aisha_done.id, patient_id=profiles[0].id, reminder_type="appointment", scheduled_for=NOW - timedelta(days=13), channel="sms", message="Reminder: Cardiology follow-up tomorrow.", status="sent", sent_at=NOW - timedelta(days=13)),
    ]
    session.add_all(reminders)

    # ── Escalations (one resolved, one open, one dismissed) ──────────────
    escalations = [
        Escalation(workflow_run_id=workflows[4].id, patient_id=profiles[3].id, severity="high", reason="emergency language detected", details="Request describes acute chest pain and asks for immediate guidance; escalated to human per safety rules.", status="open"),
        Escalation(patient_id=profiles[0].id, severity="medium", reason="medication advice requested", details="Patient asked whether they should stop taking their blood pressure medication.", status="resolved", resolved_at=NOW - timedelta(days=3), reviewed_by=staff_mitchell.id, resolution_notes="Referred patient to call cardiology office; no medication advice given by the system."),
        Escalation(patient_id=profiles[2].id, severity="low", reason="unclear request", details="Request could not be mapped to any department.", status="dismissed", resolved_at=NOW - timedelta(days=10), reviewed_by=staff_rodriguez.id, resolution_notes="Patient clarified request later; no action needed."),
    ]
    session.add_all(escalations)

    # ── Insurance policies (active / expired / inactive / none) ──────────
    policies = [
        InsurancePolicy(patient_id=profiles[0].id, provider_name="ActiveCare Health", policy_number="AC-2024-00123", plan_type="silver", active=True, valid_from=date(2024, 1, 1), valid_to=date(2026, 12, 31)),
        InsurancePolicy(patient_id=profiles[1].id, provider_name="BlueCross Community", policy_number="BC-88231", plan_type="gold", active=True, valid_from=date(2025, 3, 1), valid_to=date(2027, 2, 28)),
        InsurancePolicy(patient_id=profiles[2].id, provider_name="EuropAssist", policy_number="EA-55617", plan_type="standard", active=True, valid_from=date(2025, 6, 15), valid_to=date(2026, 6, 14)),
        InsurancePolicy(patient_id=profiles[3].id, provider_name="AlNoor Mutual", policy_number="AN-99122", plan_type="standard", active=True, valid_from=date(2023, 1, 1), valid_to=date(2024, 12, 31)),
        InsurancePolicy(patient_id=profiles[6].id, provider_name="MedShield", policy_number="MS-44509", plan_type="bronze", active=True, valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31)),
        InsurancePolicy(patient_id=profiles[7].id, provider_name="CitiCare", policy_number="CC-10233", plan_type="standard", active=False, valid_from=date(2025, 1, 1), valid_to=date(2026, 1, 1)),
    ]
    session.add_all(policies)
    session.flush()

    # ── Insurance eligibility checks (from real policy data above) ───────
    eligibility = [
        InsuranceEligibilityCheck(appointment_id=appt_aisha.id, policy_id=policies[0].id, status="covered", coverage_summary="Your ActiveCare Health silver plan covers cardiology follow-up visits. This is an eligibility estimate, not a payment guarantee.", details={"plan": "silver", "provider": "ActiveCare Health"}),
        InsuranceEligibilityCheck(appointment_id=appt_carlos.id, policy_id=policies[1].id, status="needs_pre_authorization", coverage_summary="Your BlueCross Community gold plan may cover orthopedic consultations, but a pre-authorization is required before the visit. This is an eligibility estimate, not a payment guarantee.", details={"plan": "gold", "provider": "BlueCross Community"}),
        InsuranceEligibilityCheck(appointment_id=appt_fatima.id, policy_id=policies[3].id, status="not_covered", coverage_summary="No active policy was found: the AlNoor Mutual policy on file expired on 2024-12-31. Contact your insurer or our billing office for options.", details={"reason": "policy expired"}),
    ]
    session.add_all(eligibility)

    # ── Fee schedule (source of truth for billing, per department) ───────
    fee_items = [
        FeeScheduleItem(department_id=departments[0].id, service_code="CARD-CONS", description="Cardiology consultation", amount_usd="150.00", category="consultation"),
        FeeScheduleItem(department_id=departments[0].id, service_code="CARD-FUP", description="Cardiology follow-up visit", amount_usd="110.00", category="follow_up"),
        FeeScheduleItem(department_id=departments[0].id, service_code="CARD-ECG", description="ECG interpretation", amount_usd="85.00", category="diagnostic"),
        FeeScheduleItem(department_id=departments[0].id, service_code="CARD-STRESS", description="Cardiac stress test", amount_usd="420.00", category="diagnostic"),
        FeeScheduleItem(department_id=departments[1].id, service_code="NEUR-CONS", description="Neurology consultation", amount_usd="180.00", category="consultation"),
        FeeScheduleItem(department_id=departments[1].id, service_code="NEUR-EEG", description="EEG study", amount_usd="350.00", category="diagnostic"),
        FeeScheduleItem(department_id=departments[2].id, service_code="ORTH-CONS", description="Orthopedic consultation", amount_usd="140.00", category="consultation"),
        FeeScheduleItem(department_id=departments[2].id, service_code="ORTH-XRAY", description="X-ray (single joint)", amount_usd="95.00", category="diagnostic"),
        FeeScheduleItem(department_id=departments[2].id, service_code="ORTH-PT", description="Physiotherapy session", amount_usd="75.00", category="therapy"),
        FeeScheduleItem(department_id=departments[3].id, service_code="PEDI-CONS", description="Pediatric consultation", amount_usd="120.00", category="consultation"),
        FeeScheduleItem(department_id=departments[4].id, service_code="GENE-CONS", description="General medicine consultation", amount_usd="130.00", category="consultation"),
        FeeScheduleItem(department_id=departments[4].id, service_code="GENE-LAB", description="Basic blood panel", amount_usd="60.00", category="diagnostic"),
        FeeScheduleItem(department_id=departments[5].id, service_code="DERM-CONS", description="Dermatology consultation", amount_usd="135.00", category="consultation"),
        FeeScheduleItem(department_id=departments[5].id, service_code="DERM-BIOPSY", description="Skin biopsy", amount_usd="210.00", category="procedure"),
        FeeScheduleItem(department_id=departments[6].id, service_code="RADI-MRI", description="MRI (single region)", amount_usd="980.00", category="imaging"),
        FeeScheduleItem(department_id=departments[6].id, service_code="RADI-CT", description="CT scan (single region)", amount_usd="640.00", category="imaging"),
        FeeScheduleItem(department_id=departments[6].id, service_code="RADI-US", description="Ultrasound", amount_usd="180.00", category="imaging"),
    ]
    for department in departments:
        fee_items.append(
            FeeScheduleItem(department_id=department.id, service_code="FACILITY", description="Facility fee", amount_usd="40.00", category="facility")
        )
    session.add_all(fee_items)

    # ── Billing for a completed appointment (real fee-schedule items) ────
    session.add_all([
        BillingLineItem(appointment_id=appt_aisha_done.id, description="Cardiology follow-up visit", amount_usd="110.00", category="follow_up", source="fee_schedule:CARD-FUP"),
        BillingLineItem(appointment_id=appt_aisha_done.id, description="ECG interpretation", amount_usd="85.00", category="diagnostic", source="fee_schedule:CARD-ECG"),
        BillingLineItem(appointment_id=appt_aisha_done.id, description="Facility fee", amount_usd="40.00", category="facility", source="fee_schedule:facility"),
        BillingLineItem(appointment_id=appt_priya_done.id, description="General medicine consultation", amount_usd="130.00", category="consultation", source="fee_schedule:GENE-CONS"),
        BillingLineItem(appointment_id=appt_priya_done.id, description="Basic blood panel", amount_usd="60.00", category="diagnostic", source="fee_schedule:GENE-LAB"),
    ])
    billing_explanations = [
        BillingExplanation(appointment_id=appt_aisha_done.id, summary_text="This is an estimate of expected charges for your cardiology follow-up on the dates shown. Line items come from our standard fee schedule: Cardiology follow-up visit ($110.00), ECG interpretation ($85.00), and a facility fee ($40.00). Your insurance coverage may reduce what you pay. This is an explanation of expected costs, not a legally binding invoice."),
        BillingExplanation(appointment_id=appt_priya_done.id, summary_text="This is an estimate of expected charges for your general medicine consultation: General medicine consultation ($130.00) and basic blood panel ($60.00). Your insurance coverage may reduce what you pay. This is an explanation of expected costs, not a legally binding invoice."),
    ]
    session.add_all(billing_explanations)

    # ── Audit trail ──────────────────────────────────────────────────────
    audit_events = [
        AuditEvent(actor_user_id=patients[0].id, action="patient.request_submitted", entity_type="WorkflowRun", entity_id=workflows[0].id, details={"intent": "book_appointment"}),
        AuditEvent(actor_user_id=None, action="appointment.booked", entity_type="Appointment", entity_id=appt_aisha.id, details={"department": "Cardiology", "slot_id": appt_aisha.slot_id}),
        AuditEvent(actor_user_id=None, action="document.uploaded", entity_type="PatientDocument", entity_id=documents[0].id, details={"document_type": "ecg", "duplicate": False}),
        AuditEvent(actor_user_id=None, action="document.duplicate_detected", entity_type="PatientDocument", entity_id=documents[4].id, details={"original": documents[3].id}),
        AuditEvent(actor_user_id=None, action="insurance.eligibility_checked", entity_type="InsuranceEligibilityCheck", entity_id=eligibility[0].id, details={"status": "covered"}),
        AuditEvent(actor_user_id=None, action="billing.explanation_generated", entity_type="BillingExplanation", entity_id=billing_explanations[0].id, details={"appointment_id": appt_aisha_done.id}),
        AuditEvent(actor_user_id=staff_mitchell.id, action="escalation.resolved", entity_type="Escalation", entity_id=escalations[1].id, details={"severity": "medium"}),
        AuditEvent(actor_user_id=staff_rodriguez.id, action="escalation.dismissed", entity_type="Escalation", entity_id=escalations[2].id, details={"severity": "low"}),
    ]
    session.add_all(audit_events)

    session.commit()


def print_summary(session: Session) -> None:
    print("\n=== Seed summary (real rows in PostgreSQL) ===")
    for table in reversed(Base.metadata.sorted_tables):
        count = session.execute(select(func.count()).select_from(table)).scalar_one()
        print(f"  {table.name:<30} {count:>4} rows")
    print("=== End of seed summary ===\n")


def main() -> None:
    settings = get_settings()
    print(f"Seeding database at {settings.database_url} ...")
    with SessionLocal() as session:
        seed(session)
        print_summary(session)
    print("Seeding complete.")


if __name__ == "__main__":
    main()