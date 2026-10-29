# Master Services Agreement (MSA) & Statement of Work (SOW) Template
**For Managed AI Voice Receptionist & Appointment Automation Services**

> *Disclaimer: This template is provided for operational structuring and should be reviewed by qualified legal counsel in your jurisdiction prior to execution.*

## 1. Scope of Managed Voice Services
Agency shall configure, test, deploy, and maintain an Inbound AI Voice Receptionist and Atomic Calendar Booking Middleware ("System") for Client as specified in the attached Statement of Work (SOW).
- **Covered Intents:** Up to three (3) core conversational flows (Emergency Triage/Warm Transfer, FAQ Resolution, and Live Calendar Booking).
- **Revision Cap:** Initial setup includes up to **two (2) rounds of prompt and workflow revisions**. Ongoing monthly retainer includes **one (1) structured optimization cycle per month** plus weekly transcript QA.
- **Out-of-Scope Requests:** Any additional integrations, custom CRM workflows, or scope expansions outside this SOW shall be billed via written Change Order at **$150.00 USD per hour**.

## 2. Compensation, Stripe ACH Billing & Usage Guardrails
- **Setup Fee:** `$[3,000.00]` USD (payable 50% upon execution via Stripe ACH Direct Debit and 50% upon Phase 3 Go-Live, or split into 3 monthly installments of `$[1,000.00]` USD).
- **Monthly Retainer:** `$[1,500.00]` USD per month, billed automatically via Stripe ACH.
- **Included Minute Allowance & Overage Pass-Through:** The Monthly Retainer includes up to **[1,500] connected voice minutes per month**. To protect against spam floods or viral call spikes, any usage exceeding the monthly allowance shall be billed automatically at **`$[0.20]` USD per minute**.

## 3. AI Hallucination Disclaimer & Deterministic Governance
Client acknowledges that Large Language Models (LLMs) and speech synthesis systems are probabilistic technologies. While Agency implements deterministic tool schemas, atomic slot-locking constraints, and verbal read-back gates:
1. The System is strictly prohibited from providing medical, clinical, or legal advice.
2. Client is solely responsible for verifying the accuracy of all pricing, insurance policies, operating hours, and escalation phone numbers supplied during onboarding.

## 4. TCPA, FCC & Regulatory Compliance Indemnification
1. **Inbound & Transactional SMS:** Agency configures initial AI disclosure greetings and FCC April 2025 natural-language opt-out revocation handlers (`STOP`, `UNSUBSCRIBE`, natural-language opt-outs).
2. **Client Indemnification:** Client warrants that any contact lists or outbound callback instructions provided to Agency possess valid Prior Express Consent (or Prior Express Written Consent where required under the Telephone Consumer Protection Act, 47 U.S.C. § 227). Client agrees to indemnify and hold harmless Agency against any third-party claims arising from inaccurate Client policies or unlawful Client-supplied contact lists.
