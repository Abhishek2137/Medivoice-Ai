# MediVoice Voice RAG Healthcare Appointment System

MediVoice is a voice-first appointment assistant built with FastAPI, SQLAlchemy,
PostgreSQL, ChromaDB, Groq, Faster Whisper, and React. Appointment requests are
saved separately from confirmed appointments and require a decision by the
assigned doctor.

## Local setup

1. Copy `.env.example` to `.env` and set a private `APP_SECRET_KEY` of at least
   32 characters, a random `POSTGRES_PASSWORD`, and the SMTP values described
   below. Use a URL-safe password (letters and numbers) in the local PostgreSQL
   `DATABASE_URL`.
2. Create the database `voice_rag` in your local PostgreSQL server and set
   `DATABASE_URL` to
   `postgresql+psycopg2://postgres:<password>@localhost:5432/voice_rag`.
3. Install backend dependencies and apply migrations:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   python -m alembic upgrade head
   ```

4. Start the backend and frontend in separate terminals:

   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

5. Open `http://localhost:5173`. The doctor portal is at
   `http://localhost:5173/doctor`.

The API no longer creates or upgrades tables on application startup. Apply
Alembic migrations before starting the backend.

## Existing database migration

Back up the existing PostgreSQL database before applying schema changes. This
migration is additive; it does not drop or recreate patient, doctor, or
appointment tables.

For a database created by the prior MediVoice schema, first confirm it contains
the existing `patients`, `patient_credentials`, `doctors`, `doctor_availability`,
and `appointments` tables. Then, with `DATABASE_URL` set to that database:

```powershell
cd backend
python -m alembic stamp 0001_initial
python -m alembic upgrade head
```

`stamp` records the existing schema baseline without changing its data;
`upgrade` applies the appointment-request and notification tables and indexes.
Do not stamp an empty or differently structured database. For a new database,
run only `python -m alembic upgrade head`.

## Doctor accounts

Doctors must have a registered email address on their existing doctor record.
Create their password login from a trusted backend/admin environment after
migrations have run:

```powershell
cd backend
python create_doctor_login.py --doctor-id 12 --email doctor@example.com
```

The command verifies the email against the doctor record and prompts for a
password; it does not expose a public doctor-registration endpoint. Doctors
sign in at `/doctor`. Patient and doctor sessions use separate browser tokens.

## Appointment request workflow

- Patients can select any valid future date and preferred time. A matching
  `doctor_availability` row is not required.
- The API rejects a time already occupied by a confirmed appointment. Approval
  checks again under a doctor-row lock; a partial unique database index is the
  final safeguard against concurrent confirmations.
- A pending request is stored in `appointment_requests`, never as an
  `Appointment`. Doctor approval creates a `confirmed` appointment and marks
  the request `APPROVED`. A proposed time remains `COUNTER_PROPOSED` until the
  authenticated patient accepts it; acceptance creates the confirmed
  appointment and changes the request to `CONFIRMED`. Rejections are `REJECTED`.
- Bookable slots are generated from each doctor's recurring weekday working
  windows and `appointment_duration_minutes`. Specific-date available windows
  override recurring hours; specific-date blocked periods are removed from
  either schedule. The existing `doctor_availability` table stores these date
  exceptions, while `doctor_weekly_availability` stores recurring windows.
  Dates and slots in the past and slots overlapping confirmed appointments are
  omitted. Doctors with no configured hours have an explicit empty schedule.
- Patient profile booking only accepts a generated slot. Requests are not a
  hard reservation: availability and confirmed-appointment conflicts are
  rechecked under the doctor's approval transaction, so the first valid
  approval wins and competing requests remain pending for another decision.
- Email delivery state is stored separately in `appointment_notifications`
  (`PENDING`, `SENDING`, `SENT`, or `FAILED`). Requests commit before email
  delivery. Failed deliveries remain available for authenticated retry; request
  retries do not create another appointment request.
- Doctor notification emails contain scheduling contact details and a link to
  the authenticated doctor portal. They do not include the visit reason or
  decision links. Patients must sign in to respond to a proposal.

## API endpoints

All request/decision endpoints require a bearer token and enforce patient
ownership or doctor assignment. A patient ID is never accepted as the booking
identity.

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/auth/doctor/login` | Public | Authenticate a provisioned doctor |
| `GET` | `/auth/doctor/me` | Doctor | Verify the signed-in doctor |
| `GET` | `/doctors` | Public | List profiles, consultation details, and recurring hours |
| `GET` | `/doctors/{doctor_id}` | Public | Retrieve a doctor profile |
| `GET` | `/doctors/{doctor_id}/available-dates?start_date=YYYY-MM-DD&days=60` | Public | List dates with generated open slots (maximum 90 days) |
| `GET` | `/doctors/{doctor_id}/availability?appointment_date=YYYY-MM-DD` | Public | List generated time slots for a date |
| `GET` | `/doctors/me/availability/weekly` | Doctor | Read recurring weekly working hours and slot duration |
| `PUT` | `/doctors/me/availability/weekly` | Doctor | Replace weekly hours and appointment duration |
| `GET` | `/doctors/me/availability/exceptions` | Doctor | List date-specific openings and blocked periods |
| `POST` | `/doctors/me/availability/exceptions` | Doctor | Add a date-specific opening or blocked period |
| `DELETE` | `/doctors/me/availability/exceptions/{exception_id}` | Doctor | Remove one of the doctor's own date exceptions |
| `POST` | `/appointment-requests` | Patient | Submit a request |
| `GET` | `/appointment-requests/mine` | Patient | List the patient's requests and decisions |
| `GET` | `/appointment-requests/doctor/mine` | Doctor | List requests assigned to the doctor (`pending_only=true` by default) |
| `POST` | `/appointment-requests/{id}/approve` | Assigned doctor | Approve and confirm if the requested time remains free |
| `POST` | `/appointment-requests/{id}/reject` | Assigned doctor | Reject with a required reason |
| `POST` | `/appointment-requests/{id}/counter-propose` | Assigned doctor | Suggest a future date and time |
| `POST` | `/appointment-requests/{id}/proposal-response` | Requesting patient | Accept or decline the proposal |
| `POST` | `/appointment-requests/{id}/notifications/retry` | Requesting patient | Retry pending/failed notification delivery |
| `POST` | `/appointment-requests/{id}/doctor-notifications/retry` | Assigned doctor | Retry pending/failed notification delivery |

Example patient request:

```json
{
  "doctor_id": 12,
  "requested_date": "2030-06-14",
  "requested_time": "13:30",
  "reason": "Optional reason for visit"
}
```

Send an `Idempotency-Key` header when submitting a request. Replaying the same
key and payload returns the saved request. An active duplicate request for the
same patient, doctor, date, and time receives `409 Conflict`.

The protected doctor dashboard lets doctors add multiple weekly ranges for
each weekday, configure the appointment duration, create date-specific opening
windows, block breaks or unavailable periods, and remove exceptions. Weekly
windows must not overlap and must have a valid positive duration. The
"Unavailable all day" option blocks `00:00`–`23:59` for that date.

The existing voice assistant remains available. `/voice/book` and the
compatibility `/appointment/book` route now create pending appointment requests
instead of confirmed appointments.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `APP_SECRET_KEY` | Private JWT signing key; at least 32 random characters |
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL |
| `POSTGRES_PASSWORD` | PostgreSQL password for Docker Compose |
| `PUBLIC_API_URL` | Public backend URL |
| `PUBLIC_FRONTEND_URL` | Public frontend URL used in notification email |
| `CORS_ORIGINS` | Allowed browser origins |
| `SMTP_HOST` | SMTP server |
| `SMTP_PORT` | SMTP port (typically `587`) |
| `SMTP_USERNAME` | SMTP account username |
| `SMTP_PASSWORD` | SMTP account password |
| `SMTP_FROM` | Sender address |
| `GROQ_API_KEY` | Optional Groq extraction key; demo extraction is used when unset |
| `WHISPER_MODEL` | Faster Whisper model (default `base`) |
| `WHISPER_DEVICE` | Whisper device (default `cpu`) |
| `WHISPER_COMPUTE_TYPE` | Whisper compute type (default `int8`) |
| `WHISPER_LANGUAGE` | Whisper language (default `en`) |
| `VITE_API_URL` | API URL compiled into the frontend |

Never commit `.env`, database credentials, SMTP credentials, or real signing
keys.

## Docker Compose

Set `APP_SECRET_KEY`, `POSTGRES_PASSWORD`, and any SMTP credentials in `.env`,
then run:

```powershell
docker compose up --build
```

Compose uses the PostgreSQL service as the backend database, waits for database
health before starting the API, and runs Alembic migrations before Uvicorn.
Frontend and API are available at `http://localhost:5173` and
`http://localhost:8000`.

For an existing database volume from an earlier release, back it up and stamp
the legacy baseline as described above before starting the updated backend.
Do not remove the named `postgres_data` volume.

## Tests and build

```powershell
cd backend
python -m pytest -q
```

```powershell
cd frontend
npm ci
npm run build
```

The backend tests cover requests without date-specific availability records,
invalid/past dates, duplicate submissions, notification failure/retry, authenticated doctor
decisions, patient proposal responses, ownership, and concurrent slot
confirmation protection. Availability tests cover generated recurring slots,
past-date exclusion, date-specific blocked periods, profile data, and protected
schedule management.

## Deployment notes

- Configure TLS, production CORS origins, a managed PostgreSQL service, SMTP,
  secrets management, backups, monitoring, and a notification retry/operations
  process before public deployment.
- Existing appointments remain in the `appointments` table; appointment
  requests and notification state use separate tables.
- Doctor approval and patient proposal responses are authenticated POST
  actions. Email links only open sign-in pages and never change request state.
