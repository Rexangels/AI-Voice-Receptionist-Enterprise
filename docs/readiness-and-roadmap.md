# AI Voice Receptionist: Readiness and Product Roadmap

Assessment date: 2026-10-29

## Delivery progress report

Last updated: 2026-10-29

### Implemented in the repository

- Basic customer signup, owner approval, owner/client roles, signed HTTP-only sessions, and tenant-scoped client metrics.
- Production-mode startup skips demo data; SQLite files use a persistent configured path, parent directory creation, foreign-key enforcement, WAL mode, and a busy timeout.
- Owner bootstrap no longer overwrites an existing owner's password on every restart.
- Persistent login failure throttling and signup request throttling, using hashed rate-limit keys.
- Voice booking requires an existing tenant, resource, caller details, requested time, and an explicit verbal confirmation; arbitrary unknown tools no longer report success.
- Booking lock checks account for overlapping service durations. SMS fallback now returns “sent” only after Twilio accepts the request, and requires Twilio configuration, a tenant booking URL, an unsuppressed number, and explicitly recorded SMS consent.
- Duplicate end-of-call events are ignored before a repeat SMS can be sent; webhook events with missing call, tenant, or caller identity are rejected.
- Caller-supplied text is escaped and length-limited before inclusion in TwiML.
- The container uses a non-root user, named persistent volume, and HTTP health check. The health endpoint checks database connectivity.
- Dashboard benchmark values that were not derived from live telemetry now render as unavailable instead of fabricated percentages.

### Still not production ready

- Provider webhook identity currently uses one shared secret, with an assistant-ID-to-tenant map added for production routing. Provider-specific request signature verification and per-tenant webhook credentials are still missing; do not expose this endpoint to live multi-tenant traffic yet.
- The Twilio transfer output is still a preview. It does not create a real outbound staff leg, join a conference, validate Twilio request signatures, or implement acceptance/fallback callbacks.
- Calendar availability is still locally generated. Timezone/business-hours rules and live calendar sync, cancellation, rescheduling, and resource-specific schedules are not implemented. Overlap checks currently treat naive times as UTC, so customer local-time scheduling must wait for tenant timezone configuration.
- SMS has a guarded Twilio send path, but no tenant-level booking URL management, robust consent evidence/audit trail (current transcript check is only a conservative prototype gate), delivery-status callback, inbound STOP webhook/signature verification, or end-to-end provider validation. No Twilio credentials are configured here.
- Signup email verification, password reset/recovery, invitation flow, CSRF/origin review, MFA, comprehensive audit logs, and owner account recovery remain incomplete.
- Durable schema versioning/migrations, automated backups and restore drills, production error reporting/alerting, and an incident runbook are still needed. SQLite is suitable only for a low-volume single-instance pilot; multi-instance scale needs a managed database.
- No live voice assistant, phone number, CRM, payment, calendar, contract, or onboarding automation has been connected. Workflow JSON is still configuration scaffolding.
- No production host, domain, HTTPS/reverse proxy, secrets manager, backup target, or monitoring provider has been selected/configured. Docker is not installed in this workspace, so the image and Compose deployment could not be exercised.
- No customer has agreed to a pilot. The named HVAC business remains an uncontacted lead; no outreach has been sent.
- Dental remains out of the first pilot until healthcare data handling, vendor agreements, retention, and operating procedures are reviewed for the actual deployment.

### Verification completed

- `python -m compileall -q backend/app` — passed.
- `git diff --check` — passed.
- Docker build/runtime verification — not run; Docker CLI is unavailable in this workspace.
- Live provider, security penetration, and customer acceptance checks — not run; provider accounts and deployment environment are not configured.

### Next steps

1. Select the first pilot business and configure a real HVAC/plumbing tenant, service area, hours, timezone, escalation contact, consent language, and booking URL.
2. Choose the voice platform and hosting/domain; provision secrets outside the repository. Populate `VOICE_ASSISTANT_TENANT_MAP` with real provider assistant IDs and tenant IDs, then add provider-specific webhook signature verification before live calls.
3. Complete the real calendar adapter and tested human transfer flow; confirm opt-in and SMS delivery behavior with the chosen providers.
4. Deploy to a single-instance staging environment with HTTPS, backups, monitoring, and restore validation; run an agreed call acceptance script before limited pilot traffic.
5. Qualify a prospect and obtain explicit pilot agreement before representing it as a client or enabling production traffic.

Pilot market decision: United States; HVAC/plumbing and dental are in scope. Start the first pilot with HVAC/plumbing and enable dental after healthcare data handling and vendor arrangements are reviewed.

## Executive assessment

This repository is a useful prototype and research kit. It is not ready to serve a real customer or take live calls. The code demonstrates several useful concepts, including a basic call-event handler, SQLite booking locks, opt-out recording, a demo dashboard, pricing helpers, and draft sales/onboarding materials. Some advertised integrations are only simulated, and there is no complete customer product yet.

The first release should be a tightly scoped managed pilot for one business in one vertical. Before taking live traffic, the service needs a secure tenant model, a real calendar and telephony integration, durable deployment, operational monitoring, and a human fallback. Keep regulated healthcare data out of the pilot until its data handling and vendor agreements are reviewed for the chosen jurisdiction.

## Readiness by area

| Area | Status | Current evidence and gap |
| --- | --- | --- |
| Core booking prototype | Partial | `backend/app/services/slot_locker.py` has an atomic unique-slot insert, idempotency key, required verbal confirmation, and overlapping-duration checks. Availability is still generated from fixed hours, uses UTC assumptions for naive timestamps, and does not synchronize with a customer's live calendar. |
| Voice platform | Prototype | Vapi and Retell configuration examples exist. Their webhook URLs are placeholders, credentials are absent, and there is no provider-backed call flow or end-to-end acceptance evidence. |
| Telephony and escalation | Prototype | `backend/app/api/twilio_transfer.py` builds sample TwiML and response headers. It does not establish a complete staff dial, whisper, acceptance, and merge flow. |
| SMS and CRM | Partial / not live | A Twilio SMS send path now requires configured credentials, explicit consent, a configured booking URL, and an unsuppressed number; provider delivery callbacks and tenant configuration are missing. CRM synchronization records local telemetry only. |
| User signup and access | Starter flow implemented | Workspace applications store a salted password hash and remain pending for owner review. Login uses a signed, HTTP-only cookie; password reset, email verification/notifications, rate limiting, and account recovery are still missing. |
| Agency admin and client portal | Starter views implemented | `static/admin.html` shows agency metrics and pending applications; `static/client.html` shows metrics scoped to the authenticated account's tenant. These need visual QA and broader account workflows. |
| Data and tenant isolation | Partially improved; not production ready | Authenticated customer metrics are scoped to the account's tenant and production mode no longer seeds demo data. Production voice events now bind tenant selection to the configured assistant-ID map, but still use one shared webhook secret and lack provider signatures; database hardening remains. |
| Workflow automation | Draft | The n8n JSON files describe intended stages but have placeholder/incomplete node configuration, no credentials, and no proof of payment, contract, CRM, email, or calendar events running end to end. |
| Deployment | Container packaging improved; production still pending | Docker packages the app UI and public assets, runs non-root, uses a named SQLite data volume, and has a health check. Docker could not be built here because the Docker CLI is unavailable. A real production environment, secrets, HTTPS, monitoring, backups, and provider credentials still need setup. |
| Security and operations | Starter safeguards implemented; not production ready | Owner/client roles, signed sessions, password hashing, owner approval, protected dashboard APIs, persistent auth throttles, a shared voice-webhook secret, and production secret checks are in place. Email verification, account recovery, CSRF review, provider-specific signature and tenant binding, monitoring, backups, migrations, and an incident process remain. |
| Sales readiness | Early | A pricing calculator, MSA template, and outreach playbook exist. There is no validated customer, deployed demo number, completed pilot, or verified case study. Research figures in the blueprint should be checked against primary sources and actual pilot data before being used as promises. |

## Recommended build sequence

### 0. Choose the pilot boundary

- Pick one country/market and one vertical.
- Define whether the first customer is a paid pilot, a discounted case-study pilot, or a warm design partner.
- Keep the initial call scope to inbound FAQs, lead capture, appointment requests, and human escalation.
- Agree on what the agent must never answer or do, the approved business hours, and the human fallback owner.
- Do not ingest sensitive healthcare or payment data in the first pilot unless the chosen vendors, contracts, retention settings, and operating procedures have been verified for that use.

### 1. Make the service deployable and safe

- Configure owner credentials and secrets outside source control.
- Complete Docker startup and database persistence verification in the deployment environment.
- Finish provider-specific webhook authentication and verify tenant identity from provider configuration rather than trusting call payloads.
- Add rate limits and account recovery before exposing signup publicly.
- Keep demo data limited to development; production startup now skips it.
- Add durable database migrations, backups, logs, error reporting, and a basic operational runbook.

### 2. Build the customer and agency experience

- Extend the public application flow, authenticated customer portal, and owner-only agency admin.
- Signup currently creates a pending application; an owner approval provisions a tenant. Add verified contract/payment onboarding before billing or production activation. Public signup cannot grant agency-owner rights.
- Customer portal: call outcomes, bookings, configuration/intake status, escalation settings, and support contact.
- Agency admin: aggregate metrics across tenants, client status, setup progress, usage/cost, call quality, booking conversion, escalations, and audit events.
- Design direction: cool dark slate surfaces with restrained cyan/blue accents, clear status colors, readable tables, and responsive layouts. The new starter screens use this direction and still need visual/accessibility QA.

### 3. Deliver one working voice pilot

- Connect one voice provider and one phone number to the middleware.
- Connect one real calendar for availability and booking, including duration, timezone, cancellation, and reschedule rules.
- Implement real human transfer and real SMS with opt-out enforcement and delivery logging.
- Run a sandbox call script with the customer, then limited after-hours traffic with a human fallback and agreed success measures.
- Track answer rate, booking rate, transfer rate, caller experience, failures, and verified revenue attribution.

### 4. Automate agency operations after the pilot is stable

- Connect contract/payment verification, CRM provisioning, customer intake, configuration review, deployment checklist, and welcome messages.
- Keep a human approval gate for ambiguous business rules and production activation.
- Automate recurring reports from verified telemetry and label estimates separately from confirmed revenue.
- Turn the first successful pilot into a case study with customer permission.

## First customer acquisition path

The blueprint proposes a focused vertical, after-hours call audits, a working demo line, and a short pilot with agreed success measures. We should treat these as hypotheses and validate each prospect's call handling before making claims about missed revenue. A real customer commitment requires a prospect conversation and explicit agreement; a lead list or outreach script is not a signed client.

For the first outreach batch, prepare a small list of businesses in the selected market, verify their public phone and after-hours behavior, configure a demo for that vertical, and offer a limited pilot with clear scope, data handling, price, and exit terms. Do not represent the example tenants or sample metrics in this repository as customer results.

### Initial uncontacted prospect

- **All American HVAC (Dallas–Fort Worth, Texas):** Its [company website](https://www.allamericanhvac.net/) describes a family-owned HVAC business with 24/7 emergency service and publishes `214-660-7181` and `allamericanhvac@sbcglobal.net`.
- **Why it is a candidate:** It is a US HVAC operator with emergency inbound calls, matching the first pilot vertical.
- **Qualification still needed:** The public page does not show that calls are missed or that the business wants an AI receptionist. It is a lead to qualify, not a client or endorsement. No contact has been made.

## Current decision needed to start the first product slice

The research blueprint is primarily written around US service businesses, US dollar pricing, FCC/TCPA, and healthcare examples. The selected initial market is the US, with HVAC/plumbing and dental in scope. A sensible low-complexity first pilot is HVAC/plumbing; dental workflows should follow after healthcare data handling and vendor arrangements are reviewed.

## Source notes

- This assessment compares the repository with the attached *AI Voice Receptionist Business Blueprint* and checks the implementation currently present in this checkout.
- The blueprint contains market statistics and vendor/compliance claims from mixed secondary sources. Treat them as research leads, not independently verified facts or legal advice.
- The first signup, owner dashboard, client dashboard, and container packaging slice was started after this source-level assessment. No test suite or live vendor integration has been run.
