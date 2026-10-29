import io
import json
import sys
from contextlib import redirect_stdout
from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from apps.core.models import Tenant
from apps.appointments.models import AppointmentSlotLock
from apps.compliance.models import SuppressionRegistry
from apps.telemetry.models import CallTelemetryLog, OnboardingRun
from apps.telemetry.services import generate_monthly_roi_report

# Ensure scripts dir is accessible
SCRIPTS_DIR = str(settings.BASE_DIR / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


def _json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        return {}


def system_state_endpoint(request: HttpRequest) -> JsonResponse:
    tenant_id = request.GET.get("tenant_id", "default_clinic")
    retainer_fee = float(request.GET.get("retainer_fee_usd", 1500.0))

    tenants = [
        {
            "tenant_id": t.tenant_id,
            "business_name": t.business_name,
            "vertical": t.vertical,
            "tier_name": t.tier_name,
            "retainer_fee_usd": t.retainer_fee_usd,
            "included_minutes": t.included_minutes,
            "orchestrator": t.orchestrator,
        }
        for t in Tenant.objects.all().order_by("created_at")
    ]
    bookings = [
        {
            "id": b.id,
            "tenant_id": b.tenant_id,
            "resource_id": b.resource_id,
            "slot_iso": b.slot_iso,
            "caller_name": b.caller_name,
            "service_type": b.service_type,
            "status": b.status,
            "verbal_confirmed": b.verbal_confirmed,
        }
        for b in AppointmentSlotLock.objects.filter(tenant_id=tenant_id).order_by("slot_iso")
    ]
    calls = [
        {
            "call_id": c.call_id,
            "caller_phone": c.caller_phone,
            "duration_seconds": c.duration_seconds,
            "cost_usd": c.cost_usd,
            "appointment_booked": c.appointment_booked,
            "human_transferred": c.human_transferred,
            "after_hours": c.after_hours,
            "summary": c.summary,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for c in CallTelemetryLog.objects.filter(tenant_id=tenant_id).order_by("-created_at")[:25]
    ]
    suppressions = [
        {
            "phone_number": s.phone_number,
            "revocation_phrase": s.revocation_phrase,
            "channel": s.channel,
            "revoked_at": s.revoked_at.strftime("%Y-%m-%d %H:%M"),
        }
        for s in SuppressionRegistry.objects.filter(tenant_id=tenant_id).order_by("-revoked_at")
    ]
    onboarding_runs = [
        {
            "id": r.id,
            "business_name": r.business_name,
            "vertical": r.vertical,
            "annual_revenue_band": r.annual_revenue_band,
            "setup_fee_usd": r.setup_fee_usd,
            "retainer_fee_usd": r.retainer_fee_usd,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in OnboardingRun.objects.all().order_by("-created_at")[:10]
    ]

    roi = generate_monthly_roi_report(tenant_id, retainer_fee)

    return JsonResponse({
        "tenant_id": tenant_id,
        "tenants": tenants,
        "bookings": bookings,
        "calls": calls,
        "suppressions": suppressions,
        "onboarding_runs": onboarding_runs,
        "roi": roi,
    })


def roi_report_endpoint(request: HttpRequest, tenant_id: str = "default_clinic") -> JsonResponse:
    retainer_fee = float(request.GET.get("retainer_fee_usd", 1500.0))
    report = generate_monthly_roi_report(tenant_id, retainer_fee)
    return JsonResponse(report)


@csrf_exempt
def stress_test_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    from stress_test_simulator import run_verification_suite

    buf = io.StringIO()
    with redirect_stdout(buf):
        run_verification_suite()
    return JsonResponse({"status": "passed", "output": buf.getvalue()})


@csrf_exempt
def pricing_calculator_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    from roi_and_pricing_calculator import (
        calculate_agency_floor_price,
        calculate_client_roi_and_value_price,
        evaluate_bland_tier_trap,
    )

    floor_price = calculate_agency_floor_price(
        monthly_fulfillment_hours=float(payload.get("monthly_fulfillment_hours", 8.0)),
        target_hourly_rate_usd=float(payload.get("target_hourly_rate_usd", 100.0)),
        base_tool_and_usage_cost_usd=float(payload.get("base_tool_and_usage_cost_usd", 166.67)),
    )
    client_roi = calculate_client_roi_and_value_price(
        missed_calls_per_week=int(payload.get("missed_calls_per_week", 15)),
        avg_ticket_value_usd=float(payload.get("avg_ticket_value_usd", 850.0)),
        close_rate=float(payload.get("close_rate", 0.25)),
        conservative_recovery_rate=float(payload.get("conservative_recovery_rate", 0.35)),
        agency_value_capture_share=float(payload.get("agency_value_capture_share", 0.25)),
    )
    vendor_audit = evaluate_bland_tier_trap(
        monthly_minutes=int(payload.get("monthly_minutes", 5000)),
    )
    return JsonResponse({
        "agency_floor_retainer_usd": floor_price,
        "client_roi": client_roi,
        "vendor_tier_audit": vendor_audit,
    })


@csrf_exempt
def onboard_client_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    business_name = (payload.get("business_name") or "New Service Practice").strip()
    tenant_id = (
        payload.get("tenant_id")
        or business_name.lower().replace("&", "").replace(" ", "_")[:24]
    )
    vertical = payload.get("vertical", "dental")
    revenue_band = payload.get("annual_revenue_band", "$1M - $5M")
    setup_fee_usd = float(payload.get("setup_fee_usd", 4500.0))
    retainer_fee_usd = float(payload.get("retainer_fee_usd", 1500.0))
    included_minutes = int(payload.get("included_minutes", 1500))
    avg_ticket_usd = float(payload.get("avg_ticket_usd", 550.0))
    escalation_phone = (payload.get("escalation_phone") or "").strip()
    insurance_or_dispatch_rules = (payload.get("insurance_or_dispatch_rules") or "").strip()
    operating_hours = (payload.get("operating_hours") or "Mon-Fri 8am-5pm").strip()

    initial_invoice_usd = setup_fee_usd * 0.50 + retainer_fee_usd
    stripe_ach_fee_usd = min(round(initial_invoice_usd * 0.008, 2), 5.00)
    credit_card_fee_usd = round(initial_invoice_usd * 0.029 + 0.30, 2)
    fee_saved_usd = round(credit_card_fee_usd - stripe_ach_fee_usd, 2)

    flagged_risks = []
    if not escalation_phone or len(escalation_phone) < 10:
        flagged_risks.append(
            "MISSING_ESCALATION_LINE: No valid E.164 human warm-transfer escalation number provided; defaulting to +15550123456."
        )
        escalation_phone = "+15550123456"
    if not insurance_or_dispatch_rules or len(insurance_or_dispatch_rules) < 15:
        flagged_risks.append(
            "AMBIGUOUS_QUALIFICATION_RULES: Insurance/dispatch policy is underspecified; verify exact accepted PPO plans or diagnostic dispatch fee."
        )
    if "24/7" in operating_hours.lower() and "after-hours" in insurance_or_dispatch_rules.lower():
        flagged_risks.append(
            "CONFLICTING_HOURS_RULE: Operating hours state 24/7 while intake notes reference separate after-hours rules."
        )
    if not flagged_risks:
        flagged_risks.append("ALL_RULES_VERIFIED: Deterministic and ready for sandbox stress testing.")

    orchestrator = (
        "Retell AI + Telnyx SIP (Self-Serve HIPAA BAA $0/mo)"
        if vertical in ("dental", "medical")
        else "Vapi + Telnyx SIP + Deepgram Nova-3"
    )
    hipaa_status = (
        "Active (Retell Self-Serve BAA + Zero Data Retention)"
        if vertical in ("dental", "medical")
        else "Standard Commercial + TCPA Audit Log"
    )

    kickoff_brief = f"""=== ONE-PAGE ENGINEERING KICKOFF BRIEF ===
Client: {business_name} (Tenant ID: {tenant_id})
Vertical: {vertical.upper()} | Segment: {revenue_band}
Commercial Terms: ${setup_fee_usd:,.2f} Setup + ${retainer_fee_usd:,.2f}/mo Retainer ({included_minutes} mins included)
Payment Rail: Stripe ACH Direct Debit (${stripe_ach_fee_usd:.2f} fee vs ${credit_card_fee_usd:.2f} card — Saved ${fee_saved_usd:.2f})

1. TELEPHONY & COMPLIANCE POSTURE
- Recommended Stack: {orchestrator}
- Compliance: {hipaa_status}
- Carrier Trust: SHAKEN/STIR Level A + A2P 10DLC TCR Campaign Registration
- Warm Transfer Whisper Target: {escalation_phone}

2. ATOMIC CALENDAR & GUARDRAIL CONFIGURATION
- Operating Hours: {operating_hours}
- Qualification & Pricing Policy: {insurance_or_dispatch_rules or 'Standard intake qualification'}
- Concurrency Lock: UNIQUE({tenant_id}, resource_id, slot_iso) + workflow_run_id idempotency key

3. FLAGGED ITEMS FOR LEAD ENGINEER
- """ + "\n- ".join(flagged_risks)

    tenant, _ = Tenant.objects.update_or_create(
        tenant_id=tenant_id,
        defaults={
            "business_name": business_name,
            "vertical": vertical,
            "tier_name": f"Custom Built & Operated ({revenue_band})",
            "retainer_fee_usd": retainer_fee_usd,
            "setup_fee_usd": setup_fee_usd,
            "included_minutes": included_minutes,
            "overage_rate_per_min_usd": 0.20,
            "avg_ticket_usd": avg_ticket_usd,
            "close_rate": 0.35,
            "escalation_phone": escalation_phone,
            "orchestrator": orchestrator,
            "hipaa_baa_status": hipaa_status,
        },
    )

    OnboardingRun.objects.create(
        tenant=tenant,
        business_name=business_name,
        vertical=vertical,
        annual_revenue_band=revenue_band,
        setup_fee_usd=setup_fee_usd,
        retainer_fee_usd=retainer_fee_usd,
        stripe_ach_fee_usd=stripe_ach_fee_usd,
        card_fee_saved_usd=fee_saved_usd,
        kickoff_brief=kickoff_brief,
        flagged_risks=flagged_risks,
    )

    return JsonResponse({
        "status": "PROVISIONED",
        "tenant_id": tenant_id,
        "business_name": business_name,
        "stripe_ach_fee_usd": stripe_ach_fee_usd,
        "credit_card_fee_saved_usd": fee_saved_usd,
        "flagged_risks": flagged_risks,
        "kickoff_brief": kickoff_brief,
    })


@csrf_exempt
def generate_gtm_assets_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    prospect_name = payload.get("prospect_name", "Dr. Miller")
    clinic_name = payload.get("clinic_name", "Manchester Dental & Implant Center")
    city = payload.get("city", "Manchester")
    service_focus = payload.get("service_focus", "new-patient dental implant consultation")
    avg_ticket_usd = float(payload.get("avg_ticket_usd", 450.0))
    missed_per_week = int(payload.get("missed_calls_per_week", 4))
    setup_fee_usd = float(payload.get("setup_fee_usd", 4500.0))
    retainer_fee_usd = float(payload.get("retainer_fee_usd", 1500.0))
    included_minutes = int(payload.get("included_minutes", 1500))

    monthly_leakage_usd = round(missed_per_week * 4.33 * avg_ticket_usd, 2)

    loom_script = f"""[0:00 - 0:20 | THE UNDENIABLE OBSERVATION]
"Hey {prospect_name}, I called {clinic_name}'s main line yesterday at 6:15 PM asking about a {service_focus}, and it went straight to standard voicemail. Across {city}, practices miss 20% to 30% of inbound inquiries this way—and at ${avg_ticket_usd:,.0f}+ per visit, missing just {missed_per_week} calls a week leaks over ${monthly_leakage_usd:,.0f} every single month to the practice down the road."

[0:20 - 0:55 | LIVE SPEAKERPHONE PROOF]
"I went ahead and configured an AI Receptionist specifically for {clinic_name}. Listen to how fast it picks up in under 600ms, verifies coverage, and locks an appointment atomically onto the calendar without double-booking."

[0:55 - 1:30 | ZERO-RISK 14-DAY PILOT CTA]
"I included the live test number right below this video so you can call and try interrupting it from your own cell phone. We can deploy this on your after-hours and overflow lines in 72 hours on a 14-day pilot. Reply 'PILOT' or grab 10 minutes on my calendar below." """

    msa_excerpt = f"""MASTER SERVICES AGREEMENT & STATEMENT OF WORK — {clinic_name.upper()}
1. Scope Limits: Up to 3 core conversational flows (Emergency Triage/Warm Transfer, FAQ Resolution, and Atomic Read-Offer-Lock-Write Calendar Booking).
2. Stripe ACH Compensation: ${setup_fee_usd:,.2f} Setup Fee + ${retainer_fee_usd:,.2f}/mo Retainer via Stripe ACH Direct Debit.
3. Minute Allowance: Includes {included_minutes:,} connected voice minutes/month; overages billed automatically at $0.20/minute.
4. Deterministic Governance & TCPA Compliance: Enforces verbal read-back gate prior to calendar writes, FCC Feb 2024 AI voice disclosure, and FCC April 11, 2025 natural-language opt-out revocation."""

    return JsonResponse({
        "monthly_leakage_usd": monthly_leakage_usd,
        "loom_script": loom_script,
        "msa_contract_summary": msa_excerpt,
    })

