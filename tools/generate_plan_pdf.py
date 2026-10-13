from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Voice_RAG_Healthcare_Appointment_System_Building_Plan.pdf"


def paragraph(text, style):
    return Paragraph(text.replace("\n", "<br/>"), style)


def build_pdf():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=27, leading=33, alignment=TA_CENTER, textColor=colors.HexColor("#173b35"),
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="CoverSubtitle", parent=styles["Normal"], fontSize=13, leading=19,
        alignment=TA_CENTER, textColor=colors.HexColor("#5d7069"), spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="Section", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=18, leading=23, textColor=colors.HexColor("#173b35"), spaceBefore=8,
        spaceAfter=11,
    ))
    styles.add(ParagraphStyle(
        name="Subsection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=16, textColor=colors.HexColor("#d45e42"), spaceBefore=10,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BodySmall", parent=styles["BodyText"], fontSize=9.5, leading=14,
        textColor=colors.HexColor("#273c37"), spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Note", parent=styles["BodyText"], fontSize=9, leading=13,
        leftIndent=10, borderPadding=8, backColor=colors.HexColor("#edf3ed"),
        borderColor=colors.HexColor("#b9cfbd"), borderWidth=0.5, borderRadius=2,
        spaceBefore=6, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="PlanCode", parent=styles["Code"], fontName="Courier", fontSize=7.6,
        leading=10.5, backColor=colors.HexColor("#f2f4f1"), borderPadding=8,
        borderColor=colors.HexColor("#d7dfd8"), borderWidth=0.5, spaceBefore=5,
        spaceAfter=9,
    ))

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Voice RAG Healthcare Appointment System Building Plan",
        author="OpenAI / GitHub Copilot",
    )
    story = []
    story += [Spacer(1, 34 * mm), Paragraph("VocaCare", styles["CoverTitle"])]
    story += [Paragraph("Voice-Powered RAG Healthcare Appointment Assistant", styles["CoverSubtitle"])]
    story += [Spacer(1, 12 * mm), Paragraph("End-to-end building plan", styles["CoverSubtitle"])]
    story += [Spacer(1, 35 * mm), Paragraph("A practical, portfolio-ready roadmap for building a voice-first appointment workflow with FastAPI, React, an LLM, RAG, SQL, and a doctor dashboard.", styles["Note"])]
    story += [Spacer(1, 25 * mm), Paragraph("Prototype stack: mostly free and local", styles["CoverSubtitle"]), PageBreak()]

    story += [Paragraph("1. Product Idea", styles["Section"])]
    story += [paragraph("The core workflow is: Patient speaks naturally -> speech-to-text -> structured LLM extraction -> doctor and hospital retrieval -> exact availability validation -> patient confirmation -> appointment booking -> structured summary for the doctor.", styles["BodySmall"])]
    story += [Paragraph("Example extraction", styles["Subsection"])]
    story += [Preformatted('{\n  "intent": "book_appointment",\n  "patient_name": "Rahul",\n  "specialization": "Dermatology",\n  "preferred_date": "2026-08-19",\n  "preferred_time": "17:00",\n  "symptoms": ["itching", "red patches on hands"],\n  "duration": "1 week",\n  "appointment_type": "consultation"\n}', styles["PlanCode"])]
    story += [paragraph("The doctor should receive the structured appointment summary, not the entire raw voice conversation. The original conversation can remain available behind an explicit View conversation action.", styles["BodySmall"])]

    story += [Paragraph("2. Recommended Free or Low-Cost Stack", styles["Section"])]
    stack_rows = [
        ["Layer", "Tool", "Purpose"],
        ["Frontend", "React + Vite", "Patient voice UI and doctor dashboard"],
        ["Backend", "FastAPI + Uvicorn", "API endpoints and orchestration"],
        ["Database", "PostgreSQL + SQLAlchemy", "Patients, doctors, slots, bookings"],
        ["Speech-to-text", "Whisper local", "Convert uploaded audio to text"],
        ["LLM", "Ollama local or a free-tier provider", "Intent and structured field extraction"],
        ["Vector database", "ChromaDB local", "Doctor, hospital, FAQ retrieval"],
        ["Embeddings", "Sentence Transformers", "Local semantic search embeddings"],
        ["Text-to-speech", "Browser SpeechSynthesis", "Read responses aloud at no API cost"],
        ["Validation", "Pydantic", "Typed, controlled structured output"],
        ["Development", "VS Code + Git + GitHub", "Implementation, testing, version control"],
    ]
    table = Table(stack_rows, colWidths=[30 * mm, 48 * mm, 94 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b35")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd8ce")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f0")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [table, paragraph("Start with the smallest useful set: React, FastAPI, PostgreSQL, Whisper, one LLM, ChromaDB, and Sentence Transformers. Add agent frameworks only when the workflow needs them.", styles["Note"])]

    story += [Paragraph("3. Architecture", styles["Section"])]
    story += [Preformatted("PATIENT\n   | Voice\n   v\nReact voice recorder\n   | POST /voice/transcribe\n   v\nWhisper speech-to-text\n   | transcript\n   v\nLLM extraction + missing-field logic\n   | structured JSON\n   +----------------------+\n   |                      |\n   v                      v\nChromaDB RAG          PostgreSQL\nDoctor/hospital       Exact slots and bookings\nprofiles and FAQs     Availability source of truth\n   +----------------------+\n              v\n       Appointment tools\n              |\n              v\n Confirmation + doctor summary\n", styles["PlanCode"])]
    story += [paragraph("Use RAG to answer who or what is relevant. Use PostgreSQL to decide what is actually available and to perform transactional booking. Never let the vector database be the source of truth for appointment slots.", styles["Note"])]

    story += [Paragraph("4. VS Code Project Structure", styles["Section"])]
    story += [Preformatted("voice-rag-appointment/\n|-- backend/\n|   |-- app/\n|       |-- main.py\n|       |-- api/ (voice.py, appointments.py, doctors.py, patients.py)\n|       |-- ai/ (speech.py, extractor.py, conversation.py, prompts.py)\n|       |-- rag/ (embeddings.py, vectorstore.py, retriever.py, ingest.py)\n|       |-- database/ (database.py, models.py, schemas.py)\n|       |-- services/ (appointment_service.py, doctor_service.py, patient_service.py)\n|       |-- utils/ (datetime_utils.py)\n|-- frontend/\n|   |-- src/\n|       |-- components/ (VoiceButton, Conversation, AppointmentCard, DoctorCard)\n|       |-- pages/ (PatientHome, DoctorDashboard, Appointment)\n|       |-- services/api.js\n|-- data/ (doctors.json, hospitals.json, departments.json, faq.json)\n|-- chroma_db/\n|-- README.md\n|-- .env.example\n|-- .gitignore", styles["PlanCode"])]

    story += [Paragraph("5. Build Order", styles["Section"])]
    phases = [
        ("Phase 1: Working foundation", "Install Python 3.11 or 3.12, Node.js, Git, PostgreSQL, and VS Code. Create a backend virtual environment, install FastAPI, SQLAlchemy, Pydantic, Uvicorn, and python-multipart. Confirm /docs opens."),
        ("Phase 2: Database first", "Create patients, doctors, doctor_availability, appointments, medical_context, and conversations. Seed fake doctors and schedules. PostgreSQL remains the booking source of truth."),
        ("Phase 3: Normal appointment APIs", "Implement GET /doctors, GET /doctors/{id}, GET /doctors/{id}/availability, POST /appointments, GET /appointments/{id}, DELETE /appointments/{id}, and availability checks. Test these before adding AI."),
        ("Phase 4: React patient and doctor views", "Build doctor browsing, slot selection, booking confirmation, appointment history, and the dashboard. Connect with fetch or Axios and show loading, empty, error, and success states."),
        ("Phase 5: Speech", "Record audio in the browser, upload it to POST /voice/transcribe, run Whisper locally, and return only the transcript. Test upload and transcription independently."),
        ("Phase 6: Structured extraction", "Send transcript plus current date and timezone to the LLM. Require JSON matching a Pydantic model. Missing values must be null; the model must not invent details or diagnoses."),
        ("Phase 7: Conversation filling", "Persist session state. Detect required missing fields, ask one focused question, merge the answer into the schema, and repeat until the appointment request is complete."),
        ("Phase 8: RAG", "Ingest doctor profiles, hospitals, departments, FAQs, fees, languages, and policies into ChromaDB using local embeddings. Retrieve relevant doctors and information, then check exact slots in SQL."),
        ("Phase 9: Tools and confirmation", "Expose find_doctors, check_availability, create_appointment, cancel_appointment, and reschedule_appointment as controlled backend functions. Require explicit confirmation before booking."),
        ("Phase 10: Full voice loop", "Return a concise response to React and use SpeechSynthesis to read it. Finish with an end-to-end demo: speak -> extract -> ask missing fields -> retrieve -> confirm -> book -> doctor summary."),
    ]
    for title, text in phases:
        story += [Paragraph(title, styles["Subsection"]), paragraph(text, styles["BodySmall"])]

    story += [PageBreak(), Paragraph("6. Data Design", styles["Section"])]
    story += [Preformatted("Patient\n  id, name, phone, email, age, gender, created_at\nDoctor\n  id, name, specialization, hospital, experience, consultation_fee\nDoctorAvailability\n  id, doctor_id, date, start_time, end_time, is_available\nAppointment\n  id, patient_id, doctor_id, appointment_date, appointment_time, status, symptoms, created_at\nMedicalContext\n  appointment_id, symptoms, duration, existing_conditions, medications\nConversation\n  id, patient_id, appointment_id, role, content, created_at", styles["PlanCode"])]
    story += [Paragraph("Appointment extraction schema", styles["Subsection"])]
    story += [Preformatted('{\n  "intent": "book_appointment | find_doctor | cancel | reschedule | other",\n  "patient": {"name": null, "age": null, "gender": null, "phone": null},\n  "appointment": {\n    "specialization": null, "doctor": null, "date": null, "time": null,\n    "time_preference": null, "appointment_type": "consultation"\n  },\n  "medical_context": {\n    "symptoms": [], "duration": null,\n    "existing_conditions": [], "medications": []\n  }\n}', styles["PlanCode"])]
    story += [paragraph("Use symptoms and patient-stated conditions. Do not create a disease or diagnosis field from an uncertain model guess.", styles["Note"])]

    story += [Paragraph("7. API Contract", styles["Section"])]
    api_rows = [
        ["Method", "Endpoint", "Responsibility"],
        ["POST", "/voice/transcribe", "Audio upload -> transcript"],
        ["POST", "/appointment/extract", "Transcript -> validated structured fields"],
        ["POST", "/appointment/search", "Specialization/date/time -> matching doctors and SQL slots"],
        ["POST", "/appointment/book", "Explicit confirmation -> transactional booking"],
        ["GET", "/doctor/appointments", "Doctor dashboard schedule and summaries"],
        ["GET", "/patient/appointments", "Patient appointment history"],
        ["GET", "/doctors", "Doctor profile search"],
        ["GET", "/doctors/{id}/availability", "Exact availability from SQL"],
    ]
    api_table = Table(api_rows, colWidths=[19 * mm, 60 * mm, 93 * mm], repeatRows=1)
    api_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b35")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.4),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd8ce")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f0")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [api_table]

    story += [Paragraph("8. Missing Information and Agent Flow", styles["Section"])]
    story += [paragraph("For a request such as 'I want to book a doctor's appointment', extraction should return null for name, specialization, date, and time. The conversation service asks only for the next required field, stores the answer, and re-runs extraction against the accumulated context. After retrieval, the assistant offers concrete slots. Booking happens only after the patient says yes or selects a slot.", styles["BodySmall"])]
    story += [Preformatted("1. Receive text or transcript\n2. Extract fields with null for unknown values\n3. Determine the next required field\n4. Ask one question and save the answer\n5. Repeat until patient, specialty, date, and time are known\n6. Retrieve relevant doctors with RAG\n7. Check exact availability in PostgreSQL\n8. Present choices and request confirmation\n9. Call the booking service in a transaction\n10. Generate a structured doctor summary", styles["PlanCode"])]

    story += [Paragraph("9. RAG Responsibilities", styles["Section"])]
    story += [paragraph("RAG is useful for doctor specialization, hospital information, departments, fees, languages, locations, policies, FAQs, and routing hints. It is not appropriate for exact availability, booking, cancellation, or diagnosis. For chest pain or other urgent symptoms, route the patient to appropriate urgent care or emergency guidance instead of claiming a diagnosis.", styles["BodySmall"])]
    story += [Paragraph("Ingestion pipeline", styles["Subsection"]), Preformatted("JSON and text documents\n       |\nChunk and normalize\n       |\nSentence Transformer embeddings\n       |\nChromaDB collection\n       |\nTop-k retrieval with metadata filters", styles["PlanCode"])]

    story += [Paragraph("10. Doctor Dashboard", styles["Section"])]
    story += [paragraph("The dashboard should prioritize today's schedule and concise patient context. Each appointment can show time, patient name, symptoms, duration, appointment type, status, and a View conversation action. The raw conversation is secondary; the structured summary is the primary clinical handoff for this prototype.", styles["BodySmall"])]
    story += [Preformatted("09:00 AM   Rahul Sharma\n           Symptoms: itching; red patches on hands\n           Duration: 1 week\n           Type: consultation\n           Status: confirmed\n\n10:30 AM   Priya Patil\n           Symptoms: headache; fatigue\n           Duration: 3 days", styles["PlanCode"])]

    story += [Paragraph("11. Safety and Reliability Rules", styles["Section"])]
    rules = [
        "Never invent missing patient, date, time, doctor, or symptom information.",
        "Do not diagnose. Route symptoms to an appropriate department or urgent care.",
        "Require explicit confirmation before creating an appointment.",
        "Use PostgreSQL transactions and database constraints to prevent double booking.",
        "Keep API keys in .env and exclude them from Git.",
        "Use fake data for the portfolio project; do not ingest real patient data.",
        "Log request IDs and errors without logging unnecessary sensitive medical content.",
        "Add authentication and role-based access before any real deployment.",
    ]
    for rule in rules:
        story += [paragraph("&#8226; " + rule, styles["BodySmall"])]

    story += [PageBreak(), Paragraph("12. Three-Week Roadmap", styles["Section"])]
    roadmap = [
        ["Week", "Days", "Deliverable"],
        ["1", "1-2", "Project setup, PostgreSQL schema, fake doctors and availability"],
        ["1", "3-4", "Appointment APIs and React patient/doctor screens"],
        ["1", "5-7", "Frontend integration, booking flow, error states, tests"],
        ["2", "8-9", "Whisper upload and browser recording"],
        ["2", "10-12", "LLM extraction, Pydantic validation, missing-field engine"],
        ["2", "13-14", "Appointment tools and complete voice booking"],
        ["3", "15-18", "RAG documents, embeddings, ChromaDB, retrieval"],
        ["3", "19-20", "RAG plus SQL doctor search and dashboard summaries"],
        ["3", "21", "End-to-end testing, README, demo recording, deployment review"],
    ]
    roadmap_table = Table(roadmap, colWidths=[16 * mm, 23 * mm, 133 * mm], repeatRows=1)
    roadmap_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b35")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.7),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd8ce")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f0")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [roadmap_table, Spacer(1, 12), Paragraph("Portfolio positioning", styles["Subsection"]), paragraph("The differentiator is not simply a chatbot. It is the reliable conversion of unstructured voice into a controlled appointment workflow: extraction, missing-field conversation, RAG-assisted routing, transactional availability validation, confirmation, and a useful doctor summary.", styles["BodySmall"])]
    story += [Paragraph("Recommended first implementation", styles["Section"]), paragraph("Start with the normal appointment engine and database. Then add voice transcription, structured extraction, conversational field filling, RAG, and finally the full voice response loop. This keeps every milestone demonstrable and makes debugging much easier.", styles["Note"])]

    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#71817a"))
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"{document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()