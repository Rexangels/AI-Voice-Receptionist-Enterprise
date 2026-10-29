# AI Voice Receptionist Enterprise (End-to-End Blueprint & Codebase)

An early prototype and research kit for a managed **AI voice receptionist and appointment service** for US HVAC/plumbing and dental businesses.

The repository contains a SQLite booking-lock prototype, example Vapi/Retell configurations, draft n8n workflows, a development dashboard, an owner console, a client workspace request flow, and GTM/legal planning materials. Live provider integrations, customer-grade operations, and compliance review are still required before production use.

---

## Architecture Highlights

1. **Voice configuration examples:** Draft assistant settings for Vapi and Retell. They use placeholder URLs and have not been validated against a live account.
2. **Booking-lock prototype (`backend/`):** FastAPI and SQLite code uses a unique tenant/resource/start-time constraint and idempotency key. It does not yet synchronize a real calendar or prevent every overlapping-duration conflict.
3. **Telephony examples:** TwiML builders illustrate a transfer concept. They do not provide an end-to-end tested staff dial, whisper, and conference flow.
4. **Opt-out and SMS draft:** Opt-out phrases can be recorded; the fallback function prepares a message but does not dispatch SMS through a provider.
5. **Owner and client surfaces:** The development UI includes an owner metrics console, client workspace request/approval flow, and scoped sample client view. Owner access is bootstrapped from environment variables.
6. **Agency planning kit (`workflows/`, `gtm_kit/`):** Draft onboarding/report workflows, pricing tools, outreach notes, and contract templates. Configure, validate, and review them before operational use.

---

## Repository Structure

```text
ai-voice-receptionist-enterprise/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docs/
│   └── readiness-and-roadmap.md
├── scripts/
│   ├── push_to_github.sh                # One-command script to initialize & push to your GitHub
│   ├── roi_and_pricing_calculator.py    # CLI Value-Based Pricing & Bland/Vapi Break-Even Calculator
│   └── stress_test_simulator.py         # Concurrent race-condition & idempotency verification suite
├── backend/
│   ├── Dockerfile
│   └── app/
│       ├── main.py                      # FastAPI entry point & health checks
│       ├── config.py                    # Zero-dependency environment configuration
│       ├── database.py                  # Transactional DB engine & atomic locks
│       ├── models/
│       │   └── schemas.py               # Request/Response schemas
│       ├── api/
│       │   ├── voice_webhooks.py        # Vapi/Retell live tool router & End-of-Call analyzer
│       │   └── twilio_transfer.py       # Warm transfer conference & whisper TwiML endpoints
│       └── services/
│           ├── slot_locker.py           # Read-Offer-Lock-Write atomic calendar engine
│           ├── sms_compliance.py        # TCPA revocation registry & missed-call SMS dispatcher
│           └── crm_sync.py              # Post-call structured lead & ROI telemetry logger
├── voice_configs/
│   ├── vapi/
│   │   └── assistant_config.json        # Ready-to-import Vapi Assistant payload with tool schemas
│   ├── retell/
│   │   └── agent_config.json            # Ready-to-import Retell AI Agent configuration
│   └── prompts/
│       ├── dental_clinic_prompt.md      # Production system prompt for Dental practices
│       └── hvac_plumbing_prompt.md      # Production system prompt for Home Services / HVAC
├── workflows/
│   └── n8n/
│       ├── client_onboarding_workflow.json   # Automated 5-stage client onboarding pipeline
│       └── monthly_roi_report_workflow.json  # Automated monthly client ROI email generator
└── gtm_kit/
    ├── playbooks/
    │   └── mystery_caller_loom_playbook.md   # Outbound scripts, Clay setup & discovery diagnostic
    └── contracts/
        └── master_services_agreement.md      # Agency MSA & SOW template with AI guardrails
```

---

## Quickstart (Local development)

### 1. Configure Environment
```bash
cp .env.example .env
# Set APP_SECRET_KEY and WEBHOOK_SECRET to random values of at least 32 characters.
# Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD for the agency owner.
# Add vendor credentials only when the matching integration has been configured.
```

### 2. Run with Django & Uvicorn ASGI (or Docker Compose)

**Option A — Direct Python / Django Run:**
```bash
# Run migrations (automatically handled on app.py start as well)
python manage.py migrate

# Seed initial demo data & bootstrap owner if configured
python manage.py seed_demo_data

# Start the Django ASGI server on port 3000
python app.py
```
Or use the standard Django management command:
```bash
python manage.py runserver 3000
```

**Option B — Docker Compose:**
```bash
docker compose up --build
```

Open `http://localhost:3000` (or `http://localhost:8000` in Docker) to sign in or `http://localhost:3000/signup` to request a client workspace. The owner account is created from the bootstrap values in `.env`. Applications stay pending until an owner approves them in `/admin`; this starter flow does not send approval emails yet. Development mode includes clearly marked sample records.

### 3. Product surfaces

- `/login`: sign in with owner or client credentials.
- `/signup`: client workspace request for US HVAC/plumbing and dental businesses.
- `/admin`: owner-only agency metrics and manual application review.
- `/client`: approved client's scoped call and booking summary.
- `/django-admin/`: native Django Admin panel for administrative data management.
- `/health`: health check and capability telemetry.

### 4. Run the Zero-Dependency Concurrency & Race-Condition Verification Suite
Verify that two simultaneous callers attempting to book the exact same dental chair or HVAC technician slot at the exact same millisecond never cause a double booking:
```bash
python3 scripts/stress_test_simulator.py
python3 scripts/roi_and_pricing_calculator.py
```

### 5. Publish Directly to Your GitHub
Run the included helper script:
```bash
chmod +x scripts/push_to_github.sh
./scripts/push_to_github.sh https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
```
