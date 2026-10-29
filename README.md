# AI Voice Receptionist Enterprise (End-to-End Blueprint & Codebase)

A production-grade, multi-tenant **Inbound AI Voice Receptionist & Atomic Appointment Setter** designed for local and mid-market service businesses ($1M–$20M annual revenue across Dental, Medical, HVAC, Plumbing, Legal, and Auto Repair).

This repository contains the complete technical middleware, voice orchestrator configurations (Vapi & Retell AI), n8n agency automation workflows, acoustic & concurrency stress-test harnesses, and Go-To-Market (GTM) sales and legal assets.

---

## Architecture Highlights

1. **Sub-700ms Acoustic Pipeline:** Configured for Deepgram Nova-3 streaming ASR, Claude Sonnet / GPT-4o-mini reasoning, ElevenLabs Flash / Cartesia Sonic TTS, Silero VAD, and semantic endpointing.
2. **Atomic Calendar Slot-Locking Middleware (`backend/`):** Transactional booking engine (FastAPI + SQLite/PostgreSQL compatible) that eliminates the #1 failure mode of voice agents—**double bookings from concurrent call race conditions** and **timeout-induced duplicate tool retries**—using unique database constraints (`uq_tenant_resource_slot`) and `workflow_run_id` idempotency keys.
3. **Contextual Warm Transfer & Whisper Bridge:** Twilio Programmable Voice TwiML endpoints that place callers in a conference bridge, dial human staff, whisper a 10-second AI-synthesized briefing (`"Incoming transfer: Sarah Jenkins, broken crown, verified insurance"`), and merge the call upon staff acceptance (`1`).
4. **Instant Missed-Call Text-Back & TCPA Compliance:** End-of-call webhook handlers that trigger instant SMS booking links for unbooked hang-ups and enforce FCC April 2025 natural-language opt-out revocation rules (`STOP`, `UNSUBSCRIBE`, `"take me off your list"`).
5. **Agency Ops Automation (`workflows/n8n/`):** Importable n8n JSON workflows for 60-second client onboarding (Stripe ACH + Contract webhook -> CRM + Portal + Claude/Gemini Kickoff Brief) and automated monthly executive ROI reporting.
6. **GTM & Legal Kit (`gtm_kit/`):** Interactive ROI & Floor-Price Calculator, After-Hours Mystery Caller Loom scripts, Clay waterfall enrichment schemas, and a Master Services Agreement (MSA) with AI hallucination indemnification and minute-overage guardrails.

---

## Repository Structure

```text
ai-voice-receptionist-enterprise/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
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

## Quickstart (Local or Production VPS)

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Vapi/Retell, Twilio/Telnyx, and Calendar credentials
```

### 2. Run with Docker Compose (or Uvicorn)
```bash
docker-compose up --build -d
```
The atomic middleware API will be live at `http://localhost:8000` (Swagger docs at `http://localhost:8000/docs`).

### 3. Run the Zero-Dependency Concurrency & Race-Condition Verification Suite
Verify that two simultaneous callers attempting to book the exact same dental chair or HVAC technician slot at the exact same millisecond never cause a double booking:
```bash
python3 scripts/stress_test_simulator.py
python3 scripts/roi_and_pricing_calculator.py
```

### 4. Publish Directly to Your GitHub
Run the included helper script:
```bash
chmod +x scripts/push_to_github.sh
./scripts/push_to_github.sh https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
```
