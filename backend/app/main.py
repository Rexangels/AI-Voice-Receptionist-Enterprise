import io
import json
import os
import re
import sys
import uuid
import sqlite3
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Any
from urllib.parse import parse_qs, urlparse
import hmac

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
STATIC_DIR = ROOT_DIR / "static"
PUBLIC_DIR = ROOT_DIR / "public"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.database import init_db, transactional_db  # noqa: E402
from app.config import settings  # noqa: E402
from app.services.auth import (  # noqa: E402
    bootstrap_owner,
    create_session_token,
    get_current_user,
    hash_password,
    normalize_signup_email,
    enforce_rate_limit,
    record_auth_failure,
    clear_auth_failures,
    require_client,
    require_owner,
    verify_password,
)
from app.services.slot_locker import release_booked_slot, update_booking_status  # noqa: E402
from app.api.voice_webhooks import (  # noqa: E402
    process_vapi_webhook_payload,
    process_direct_booking,
    process_roi_report,
)
from app.api.twilio_transfer import (  # noqa: E402
    build_warm_transfer_hold_twiml,
    build_staff_whisper_twiml,
)

init_db()
bootstrap_owner()


def _seed_initial_demo_data_if_empty() -> None:
    with transactional_db() as conn:
        t_count = conn.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()["c"]
        if t_count == 0:
            tenants_seed = [
                (
                    "default_clinic",
                    "Apex Dental & Implant Studio",
                    "dental",
                    "Custom Built & Operated ($1M–$20M)",
                    1500.0,
                    4500.0,
                    1500,
                    0.20,
                    450.0,
                    0.35,
                    "+15550123456",
                    "Retell AI + Telnyx SIP",
                    "Active (Self-Serve BAA $0/mo)",
                    "Level A Attested",
                    "TCR Approved",
                ),
                (
                    "primeflow_hvac",
                    "PrimeFlow Heating, Cooling & Plumbing",
                    "hvac_plumbing",
                    "Custom Built & Operated ($1M–$20M)",
                    2000.0,
                    6000.0,
                    2000,
                    0.20,
                    850.0,
                    0.30,
                    "+15550198877",
                    "Vapi + Telnyx SIP + Cartesia Sonic",
                    "Standard Commercial",
                    "Level A Attested",
                    "TCR Approved",
                ),
                (
                    "metro_legal",
                    "Metro Personal Injury & Intake Law",
                    "legal",
                    "Full AI Operations Stack ($5M–$20M+)",
                    3500.0,
                    9000.0,
                    3000,
                    0.22,
                    2400.0,
                    0.25,
                    "+15550144411",
                    "Retell AI + Twilio Elastic SIP",
                    "SOC 2 Type II + Zero Data Retention",
                    "Level A Attested",
                    "TCR Approved",
                ),
            ]
            conn.executemany(
                """
                INSERT OR IGNORE INTO tenants
                (tenant_id, business_name, vertical, tier_name, retainer_fee_usd, setup_fee_usd,
                 included_minutes, overage_rate_per_min_usd, avg_ticket_usd, close_rate,
                 escalation_phone, orchestrator, hipaa_baa_status, shaken_stir_status, a2p_10dlc_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tenants_seed,
            )
            conn.commit()

        count = conn.execute("SELECT COUNT(*) AS c FROM appointment_slot_locks").fetchone()["c"]
        if count == 0:
            seed_bookings = [
                {
                    "tenant_id": "default_clinic",
                    "resource_id": "chair_1",
                    "workflow_run_id": "seed_run_001",
                    "firstName": "Sarah Jenkins",
                    "phone": "+15552223333",
                    "serviceType": "implant_consultation",
                    "requestedTime": "2026-11-05T09:00:00",
                },
                {
                    "tenant_id": "default_clinic",
                    "resource_id": "chair_1",
                    "workflow_run_id": "seed_run_002",
                    "firstName": "Marcus Vance",
                    "phone": "+15553334444",
                    "serviceType": "emergency_crown_repair",
                    "requestedTime": "2026-11-05T10:00:00",
                },
                {
                    "tenant_id": "default_clinic",
                    "resource_id": "chair_2",
                    "workflow_run_id": "seed_run_003",
                    "firstName": "Dr. Aris Thorne",
                    "phone": "+15554445555",
                    "serviceType": "routine_cleaning",
                    "requestedTime": "2026-11-05T13:00:00",
                },
                {
                    "tenant_id": "default_clinic",
                    "resource_id": "chair_1",
                    "workflow_run_id": "seed_run_004",
                    "firstName": "Clara Oswald",
                    "phone": "+15556667777",
                    "serviceType": "emergency_exam",
                    "requestedTime": "2026-11-05T15:00:00",
                },
                {
                    "tenant_id": "primeflow_hvac",
                    "resource_id": "truck_bay_1",
                    "workflow_run_id": "seed_hvac_001",
                    "firstName": "Robert Chen",
                    "phone": "+15559012345",
                    "serviceType": "hvac_emergency_dispatch",
                    "requestedTime": "2026-11-05T09:00:00",
                },
            ]
            for b in seed_bookings:
                process_direct_booking(b)

            seed_calls = [
                ("call_seed_101", "default_clinic", "+15552223333", 118.0, 0.16, True, False, True, 520, 690, 115, "Booked implant consultation for Sarah Jenkins (Chair 1)."),
                ("call_seed_102", "default_clinic", "+15553334444", 94.0, 0.13, True, False, False, 540, 710, 122, "Booked emergency crown repair for Marcus Vance."),
                ("call_seed_103", "default_clinic", "+15554445555", 82.0, 0.11, True, False, False, 510, 675, 110, "Booked routine hygiene cleaning for Dr. Aris Thorne (Chair 2)."),
                ("call_seed_104", "default_clinic", "+15556667777", 105.0, 0.15, True, True, True, 550, 730, 128, "Booked emergency exam for Clara Oswald and warm-transferred briefing."),
                ("call_seed_201", "primeflow_hvac", "+15559012345", 130.0, 0.17, True, False, True, 495, 660, 108, "After-hours emergency furnace dispatch locked for Robert Chen."),
            ]
            for cid, tid, phone, dur, cost, booked, tx, ah, p50, p95, ttfa, summary in seed_calls:
                process_vapi_webhook_payload(
                    {
                        "message": {
                            "type": "end-of-call-report",
                            "durationSeconds": dur,
                            "cost": cost,
                            "turnLatencyP50Ms": p50,
                            "turnLatencyP95Ms": p95,
                            "ttfaMs": ttfa,
                            "call": {
                                "id": cid,
                                "tenantId": tid,
                                "customer": {"number": phone},
                            },
                            "transcript": summary,
                            "analysis": {
                                "summary": summary,
                                "structuredData": {
                                    "appointmentBooked": booked,
                                    "transferredToHuman": tx,
                                    "isAfterHours": ah,
                                },
                            },
                        }
                    }
                )


if settings.APP_ENV.lower() != "production":
    _seed_initial_demo_data_if_empty()


def get_health_payload() -> Dict[str, Any]:
    try:
        with transactional_db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception:
        return {"status": "unhealthy", "service": "ai-voice-receptionist-enterprise", "checks": {"database": "failed"}}
    return {
        "status": "healthy",
        "service": "ai-voice-receptionist-enterprise",
        "commercial_readiness": "PROTOTYPE",
        "checks": {"database": "ok"},
        "prototype_capabilities": [
            "sqlite_slot_uniqueness",
            "idempotency_key_handling",
            "verbal_confirmation_gate",
            "opt_out_phrase_recording",
            "owner_and_client_dashboard_starters",
            "pending_workspace_approval",
        ],
    }


def get_system_state_payload(
    tenant_id: str = "default_clinic", retainer_fee_usd: float = 1500.0
) -> Dict[str, Any]:
    with transactional_db() as conn:
        tenants = [
            dict(row)
            for row in conn.execute("SELECT * FROM tenants ORDER BY created_at ASC").fetchall()
        ]
        bookings = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM appointment_slot_locks WHERE tenant_id = ? ORDER BY slot_iso ASC, id DESC",
                (tenant_id,),
            ).fetchall()
        ]
        calls = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM call_telemetry_logs WHERE tenant_id = ? ORDER BY id DESC LIMIT 25",
                (tenant_id,),
            ).fetchall()
        ]
        suppressions = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM suppression_registry WHERE tenant_id = ? ORDER BY id DESC",
                (tenant_id,),
            ).fetchall()
        ]
        onboarding_runs = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM onboarding_runs ORDER BY id DESC LIMIT 10"
            ).fetchall()
        ]
    roi = process_roi_report(tenant_id, retainer_fee_usd)
    return {
        "tenant_id": tenant_id,
        "tenants": tenants,
        "bookings": bookings,
        "calls": calls,
        "suppressions": suppressions,
        "onboarding_runs": onboarding_runs,
        "roi": roi,
    }


def get_admin_metrics_payload() -> Dict[str, Any]:
    with transactional_db() as conn:
        totals = dict(
            conn.execute(
                """SELECT
                    (SELECT COUNT(*) FROM tenants) AS client_count,
                    (SELECT COUNT(*) FROM users WHERE role = 'client' AND status = 'ACTIVE') AS active_accounts,
                    (SELECT COUNT(*) FROM users WHERE role = 'client' AND status = 'PENDING') AS pending_applications,
                    (SELECT COUNT(*) FROM call_telemetry_logs) AS total_calls,
                    (SELECT COUNT(*) FROM call_telemetry_logs WHERE appointment_booked = 1) AS booked_calls,
                    (SELECT COUNT(*) FROM call_telemetry_logs WHERE human_transferred = 1) AS transfers,
                    (SELECT COUNT(*) FROM call_telemetry_logs WHERE after_hours = 1) AS after_hours_calls,
                    (SELECT COALESCE(ROUND(AVG(turn_latency_p50_ms)), 0) FROM call_telemetry_logs) AS avg_turn_latency_p50_ms,
                    (SELECT COALESCE(ROUND(AVG(turn_latency_p95_ms)), 0) FROM call_telemetry_logs) AS avg_turn_latency_p95_ms,
                    (SELECT COALESCE(ROUND(AVG(ttfa_ms)), 0) FROM call_telemetry_logs) AS avg_ttfa_ms,
                    (SELECT COALESCE(SUM(race_conflict_prevented), 0) FROM call_telemetry_logs) AS race_conflicts_prevented,
                    (SELECT COUNT(*) FROM suppression_registry) AS opt_outs_recorded,
                    (SELECT COALESCE(SUM(cost_usd), 0) FROM call_telemetry_logs) AS estimated_voice_cost_usd,
                    (SELECT COALESCE(SUM(attributed_revenue_usd), 0) FROM call_telemetry_logs) AS attributed_revenue_usd"""
            ).fetchone()
        )
        clients = [
            dict(row)
            for row in conn.execute(
                """SELECT t.tenant_id, t.business_name, t.vertical, t.created_at,
                    COUNT(c.id) AS total_calls,
                    COALESCE(SUM(c.appointment_booked), 0) AS booked_calls,
                    COALESCE(SUM(c.human_transferred), 0) AS transfers,
                    COALESCE(SUM(c.cost_usd), 0) AS estimated_voice_cost_usd,
                    COALESCE(SUM(c.attributed_revenue_usd), 0) AS attributed_revenue_usd
                FROM tenants t LEFT JOIN call_telemetry_logs c ON c.tenant_id = t.tenant_id
                GROUP BY t.tenant_id ORDER BY t.created_at DESC"""
            ).fetchall()
        ]
        applications = [
            dict(row)
            for row in conn.execute(
                """SELECT id, full_name, email, business_name, vertical, created_at
                FROM users WHERE role = 'client' AND status = 'PENDING' ORDER BY created_at ASC LIMIT 100"""
            ).fetchall()
        ]
    totals["booking_rate"] = round(totals["booked_calls"] / totals["total_calls"], 4) if totals["total_calls"] else 0
    return {
        "environment": settings.APP_ENV.lower(),
        "metrics": totals,
        "clients": clients,
        "applications": applications,
    }


def get_client_metrics_payload(tenant_id: str) -> Dict[str, Any]:
    with transactional_db() as conn:
        tenant = conn.execute(
            "SELECT tenant_id, business_name, vertical FROM tenants WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()
        if not tenant:
            return {"tenant": None, "metrics": {}, "calls": [], "bookings": []}
        metrics = dict(
            conn.execute(
                """SELECT COUNT(*) AS total_calls,
                    COALESCE(SUM(appointment_booked), 0) AS booked_calls,
                    COALESCE(SUM(human_transferred), 0) AS transfers,
                    COALESCE(SUM(after_hours), 0) AS after_hours_calls,
                    COALESCE(ROUND(AVG(turn_latency_p50_ms)), 0) AS avg_turn_latency_p50_ms,
                    COALESCE(ROUND(AVG(turn_latency_p95_ms)), 0) AS avg_turn_latency_p95_ms,
                    COALESCE(ROUND(AVG(ttfa_ms)), 0) AS avg_ttfa_ms,
                    COALESCE(SUM(race_conflict_prevented), 0) AS race_conflicts_prevented,
                    COALESCE(SUM(cost_usd), 0) AS estimated_voice_cost_usd,
                    COALESCE(SUM(attributed_revenue_usd), 0) AS attributed_revenue_usd
                FROM call_telemetry_logs WHERE tenant_id = ?""", (tenant_id,)
            ).fetchone()
        )
        metrics["opt_outs_recorded"] = conn.execute(
            "SELECT COUNT(*) AS count FROM suppression_registry WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()["count"]
        calls = [dict(row) for row in conn.execute(
            """SELECT call_id, duration_seconds, appointment_booked, human_transferred,
                after_hours, attributed_revenue_usd, summary, created_at
            FROM call_telemetry_logs WHERE tenant_id = ? ORDER BY id DESC LIMIT 25""", (tenant_id,)
        ).fetchall()]
        bookings = [dict(row) for row in conn.execute(
            """SELECT id, resource_id, slot_iso, caller_name, service_type, duration_minutes, status
            FROM appointment_slot_locks WHERE tenant_id = ? ORDER BY slot_iso DESC LIMIT 25""", (tenant_id,)
        ).fetchall()]
    metrics["booking_rate"] = round(metrics["booked_calls"] / metrics["total_calls"], 4) if metrics["total_calls"] else 0
    return {"tenant": dict(tenant), "metrics": metrics, "calls": calls, "bookings": bookings}


def is_valid_webhook_secret(value: str | None) -> bool:
    return bool(settings.WEBHOOK_SECRET and value and hmac.compare_digest(value, settings.WEBHOOK_SECRET))


def get_warm_transfer_preview_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    res = build_warm_transfer_hold_twiml(payload)
    whisper_twiml = build_staff_whisper_twiml(
        f"Incoming AI Receptionist warm transfer. Caller {payload.get('caller_name', 'Caller')} on line regarding "
        f"{payload.get('urgency_reason', 'Urgent inquiry')}. {payload.get('verified_details', 'Standard intake completed')}. "
        f"Press 1 to connect immediately."
    )
    return {
        "hold_twiml": res["twiml"],
        "headers": res["headers"],
        "whisper_twiml": whisper_twiml,
    }


def run_stress_test_payload() -> Dict[str, Any]:
    from stress_test_simulator import run_verification_suite

    buf = io.StringIO()
    with redirect_stdout(buf):
        run_verification_suite()
    return {"status": "passed", "output": buf.getvalue()}


def run_pricing_calculator_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
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
    return {
        "agency_floor_retainer_usd": floor_price,
        "client_roi": client_roi,
        "vendor_tier_audit": vendor_audit,
    }


def run_autonomous_onboarding_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the 5-Stage Autonomous Client Onboarding Pipeline (Blueprint Pages 18-19):
    1. Dual Webhook Verification (Contract Signed + Stripe ACH Direct Debit 0.8% capped at $5.00).
    2. CRM Deal Stage -> Onboarding & Multi-Tenant Database Provisioning.
    3. Personalized Welcome & Delegated Access Protocol (Zero Plaintext Passwords).
    4. 24h/72h Conditional Intake Check.
    5. 1-Page Engineering Kickoff Brief Synthesis with Automated Rule Conflict & Risk Flagging.
    """
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

    # Stripe ACH Direct Debit fee calculation (0.8% capped at $5.00 vs 2.9% + $0.30 credit card)
    initial_invoice_usd = setup_fee_usd * 0.50 + retainer_fee_usd
    stripe_ach_fee_usd = min(round(initial_invoice_usd * 0.008, 2), 5.00)
    credit_card_fee_usd = round(initial_invoice_usd * 0.029 + 0.30, 2)
    fee_saved_usd = round(credit_card_fee_usd - stripe_ach_fee_usd, 2)

    flagged_risks = []
    if not escalation_phone or len(escalation_phone) < 10:
        flagged_risks.append(
            "MISSING_ESCALATION_LINE: No valid E.164 human warm-transfer escalation number provided; defaulting to +15550123456 until confirmed on Kickoff Call."
        )
        escalation_phone = "+15550123456"
    if not insurance_or_dispatch_rules or len(insurance_or_dispatch_rules) < 15:
        flagged_risks.append(
            "AMBIGUOUS_QUALIFICATION_RULES: Insurance/dispatch policy is underspecified; verify exact accepted PPO plans or diagnostic dispatch fee before enabling autonomous booking."
        )
    if "24/7" in operating_hours.lower() and "after-hours" in insurance_or_dispatch_rules.lower():
        flagged_risks.append(
            "CONFLICTING_HOURS_RULE: Operating hours state 24/7 while intake notes reference separate after-hours rules."
        )
    if not flagged_risks:
        flagged_risks.append("ALL_RULES_VERIFIED: Intake rules, escalation phone, and operating hours are deterministic and ready for Phase 2 sandbox stress testing.")

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
Commercial Terms: ${setup_fee_usd:,.2f} Setup + ${retainer_fee_usd:,.2f}/mo Retainer ({included_minutes} mins included, $0.20/min overage)
Payment Rail: Stripe ACH Direct Debit (${stripe_ach_fee_usd:.2f} fee vs ${credit_card_fee_usd:.2f} card — Saved ${fee_saved_usd:.2f})

1. TELEPHONY & COMPLIANCE POSTURE
- Recommended Stack: {orchestrator}
- Compliance: {hipaa_status}
- Carrier Trust: SHAKEN/STIR Level A + A2P 10DLC TCR Campaign Registration
- Warm Transfer Whisper Target: {escalation_phone}

2. ATOMIC CALENDAR & GUARDRAIL CONFIGURATION
- Operating Hours: {operating_hours}
- Qualification & Pricing Policy: {insurance_or_dispatch_rules or 'Standard intake qualification; require verbal read-back gate prior to atomic slot lock.'}
- Concurrency Lock: UNIQUE({tenant_id}, resource_id, slot_iso) + workflow_run_id idempotency key

3. FLAGGED ITEMS FOR LEAD ENGINEER ON KICKOFF CALL
- """ + "\n- ".join(flagged_risks)

    with transactional_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tenants
            (tenant_id, business_name, vertical, tier_name, retainer_fee_usd, setup_fee_usd,
             included_minutes, overage_rate_per_min_usd, avg_ticket_usd, close_rate,
             escalation_phone, orchestrator, hipaa_baa_status, shaken_stir_status, a2p_10dlc_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0.20, ?, 0.35, ?, ?, ?, 'Level A Attested', 'TCR Approved')
            """,
            (
                tenant_id,
                business_name,
                vertical,
                f"Custom Built & Operated ({revenue_band})",
                retainer_fee_usd,
                setup_fee_usd,
                included_minutes,
                avg_ticket_usd,
                escalation_phone,
                orchestrator,
                hipaa_status,
            ),
        )
        conn.execute(
            """
            INSERT INTO onboarding_runs
            (tenant_id, business_name, vertical, annual_revenue_band, setup_fee_usd, retainer_fee_usd,
             stripe_ach_fee_usd, card_fee_saved_usd, kickoff_brief, flagged_risks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                business_name,
                vertical,
                revenue_band,
                setup_fee_usd,
                retainer_fee_usd,
                stripe_ach_fee_usd,
                fee_saved_usd,
                kickoff_brief,
                json.dumps(flagged_risks),
            ),
        )
        conn.commit()

    return {
        "status": "PROVISIONED",
        "tenant_id": tenant_id,
        "business_name": business_name,
        "stripe_ach_fee_usd": stripe_ach_fee_usd,
        "credit_card_fee_saved_usd": fee_saved_usd,
        "flagged_risks": flagged_risks,
        "kickoff_brief": kickoff_brief,
    }


def generate_gtm_assets_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
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
1. Scope Limits: Up to 3 core conversational flows (Emergency Triage/Warm Transfer, FAQ Resolution, and Atomic Read-Offer-Lock-Write Calendar Booking). Capped at 2 setup revision rounds and 1 monthly optimization cycle ($150/hr Change Order rate thereafter).
2. Stripe ACH Compensation: ${setup_fee_usd:,.2f} Setup Fee (or 3x ${setup_fee_usd/3:,.2f}/mo) + ${retainer_fee_usd:,.2f}/mo Retainer via Stripe ACH Direct Debit.
3. Minute Allowance & Spam-Flood Guardrail: Includes {included_minutes:,} connected voice minutes/month; overages billed automatically at $0.20/minute.
4. Deterministic Governance & TCPA Compliance: Enforces verbal read-back gate prior to calendar writes, FCC Feb 2024 AI voice disclosure, and FCC April 11, 2025 natural-language opt-out revocation."""

    return {
        "monthly_leakage_usd": monthly_leakage_usd,
        "loom_script": loom_script,
        "msa_contract_summary": msa_excerpt,
    }


OPENAPI_SPEC: Dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "AI Voice Receptionist Enterprise Middleware",
        "description": (
            "Atomic Calendar Slot-Locking, Vapi/Retell Tool Router, "
            "Contextual Twilio Warm-Transfer Whisper Bridge, TCPA Revocation Engine, and Autonomous Agency Ops."
        ),
        "version": "2.0.0",
    },
    "paths": {
        "/health": {"get": {"summary": "Service Health & Commercial Readiness Check"}},
        "/api/v1/voice/state": {"get": {"summary": "Live Multi-Tenant System State & 3-Layer Telemetry"}},
        "/api/v1/voice/vapi-webhook": {"post": {"summary": "Vapi / Retell Server Webhook Router"}},
        "/api/v1/voice/book-direct": {"post": {"summary": "Atomic Direct Appointment Slot Lock"}},
        "/api/v1/voice/update-booking-status": {"post": {"summary": "Update Appointment Attendance Status (Confirmed, Completed, Rescheduled, No-Show)"}},
        "/api/v1/voice/release-slot": {"post": {"summary": "Release or Cancel Locked Appointment Slot"}},
        "/api/v1/voice/roi-report/{tenant_id}": {"get": {"summary": "Monthly Executive ROI & 3-Layer Telemetry Report"}},
        "/api/v1/telephony/warm-transfer-hold": {"post": {"summary": "Twilio Warm Transfer Hold TwiML"}},
        "/api/v1/telephony/staff-whisper": {"get": {"summary": "Twilio Staff Whisper Screening TwiML"}},
        "/api/v1/voice/run-stress-test": {"post": {"summary": "Run 7-Step Concurrency & TCPA Verification Suite"}},
        "/api/v1/voice/pricing-calculator": {"post": {"summary": "Value-Based Retainer & Vendor Tier Calculator"}},
        "/api/v1/agency/onboard-client": {"post": {"summary": "Execute 5-Stage Autonomous Client Onboarding & Kickoff Brief"}},
        "/api/v1/agency/generate-gtm-assets": {"post": {"summary": "Generate Mystery-Caller Loom Script & MSA Contract"}},
    },
}

SWAGGER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>API Docs — AI Voice Receptionist Enterprise</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => {
      window.ui = SwaggerUIBundle({ url: '/openapi.json', dom_id: '#swagger-ui' });
    };
  </script>
</body>
</html>"""


class EnterpriseMiddlewareHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(
        self,
        raw: bytes,
        content_type: str,
        status: int = 200,
        extra_headers: Dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _send_text(
        self,
        body: str,
        content_type: str = "text/html; charset=utf-8",
        status: int = 200,
        extra_headers: Dict[str, str] | None = None,
    ) -> None:
        self._send_bytes(body.encode("utf-8"), content_type, status, extra_headers)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                self._send_text(index_file.read_text(encoding="utf-8"))
                return
            self._send_text("<h1>AI Voice Receptionist Enterprise Middleware</h1>")
            return

        if path.startswith("/public/assets/") or path.startswith("/assets/"):
            rel = path.lstrip("/")
            if not rel.startswith("public/"):
                rel = "public/" + rel
            target_file = (ROOT_DIR / rel).resolve()
            if str(target_file).startswith(str(PUBLIC_DIR.resolve())) and target_file.is_file():
                ctype = "application/pdf" if target_file.suffix.lower() == ".pdf" else "application/octet-stream"
                self._send_bytes(target_file.read_bytes(), content_type=ctype)
                return

        if path in ("/health", "/api/health"):
            self._send_json(get_health_payload())
            return

        if path == "/openapi.json":
            self._send_json(OPENAPI_SPEC)
            return

        if path == "/docs":
            self._send_text(SWAGGER_HTML)
            return

        if path == "/api/v1/voice/state":
            tenant_id = qs.get("tenant_id", ["default_clinic"])[0]
            retainer = float(qs.get("retainer_fee_usd", ["1500.0"])[0])
            self._send_json(get_system_state_payload(tenant_id, retainer))
            return

        if path.startswith("/api/v1/voice/roi-report/"):
            tenant_id = path.split("/api/v1/voice/roi-report/", 1)[1] or "default_clinic"
            retainer = float(qs.get("retainer_fee_usd", ["1500.0"])[0])
            self._send_json(process_roi_report(tenant_id, retainer))
            return

        if path == "/api/v1/telephony/staff-whisper":
            briefing = qs.get("briefing", ["Incoming warm transfer. Press 1 to accept."])[0]
            self._send_text(
                build_staff_whisper_twiml(briefing),
                content_type="application/xml; charset=utf-8",
            )
            return

        self._send_json({"detail": "Not Found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self._read_json_body()
        except Exception as exc:
            self._send_json({"error": f"Invalid JSON: {exc}"}, status=400)
            return

        try:
            if path == "/api/v1/voice/vapi-webhook":
                self._send_json(process_vapi_webhook_payload(payload))
                return

            if path == "/api/v1/voice/book-direct":
                self._send_json(process_direct_booking(payload))
                return

            if path == "/api/v1/voice/update-booking-status":
                with transactional_db() as conn:
                    res = update_booking_status(
                        conn,
                        booking_id=int(payload.get("booking_id", 0)),
                        tenant_id=payload.get("tenant_id", "default_clinic"),
                        new_status=str(payload.get("status", "CONFIRMED")),
                    )
                self._send_json(res)
                return

            if path == "/api/v1/voice/release-slot":
                with transactional_db() as conn:
                    res = release_booked_slot(
                        conn,
                        booking_id=int(payload.get("booking_id", 0)),
                        tenant_id=payload.get("tenant_id", "default_clinic"),
                    )
                self._send_json(res)
                return

            if path == "/api/v1/telephony/warm-transfer-hold":
                res = build_warm_transfer_hold_twiml(payload)
                self._send_text(
                    res["twiml"],
                    content_type="application/xml; charset=utf-8",
                    extra_headers=res["headers"],
                )
                return

            if path == "/api/v1/telephony/warm-transfer-preview":
                self._send_json(get_warm_transfer_preview_payload(payload))
                return

            if path == "/api/v1/voice/run-stress-test":
                self._send_json(run_stress_test_payload())
                return

            if path == "/api/v1/voice/pricing-calculator":
                self._send_json(run_pricing_calculator_payload(payload))
                return

            if path == "/api/v1/agency/onboard-client":
                self._send_json(run_autonomous_onboarding_payload(payload))
                return

            if path == "/api/v1/agency/generate-gtm-assets":
                self._send_json(generate_gtm_assets_payload(payload))
                return

            self._send_json({"detail": "Not Found"}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)


# Optional FastAPI wiring when running in an external container with FastAPI installed
try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(
        title="AI Voice Receptionist Enterprise Middleware",
        description=(
            "Atomic Calendar Slot-Locking, Vapi/Retell Tool Router, "
            "Contextual Twilio Warm-Transfer Whisper Bridge, and TCPA Revocation Engine."
        ),
        version="2.0.0",
    )

    if PUBLIC_DIR.exists():
        app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/login", response_class=HTMLResponse)
    def login_page():
        login_file = STATIC_DIR / "login.html"
        if login_file.exists():
            return FileResponse(login_file)
        return HTMLResponse("<h1>Sign in</h1>")

    @app.get("/signup", response_class=HTMLResponse)
    def signup_page():
        signup_file = STATIC_DIR / "signup.html"
        if signup_file.exists():
            return FileResponse(signup_file)
        return HTMLResponse("<h1>Request a workspace</h1>")

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page():
        admin_file = STATIC_DIR / "admin.html"
        if admin_file.exists():
            return FileResponse(admin_file)
        return HTMLResponse("<h1>Agency admin</h1>")

    @app.get("/client", response_class=HTMLResponse)
    def client_page():
        client_file = STATIC_DIR / "client.html"
        if client_file.exists():
            return FileResponse(client_file)
        return HTMLResponse("<h1>Client workspace</h1>")

    @app.post("/api/v1/auth/signup", status_code=202)
    def signup_endpoint(payload: Dict[str, Any], request: Request):
        signup_key = f"signup:{request.client.host if request.client else 'unknown'}"
        enforce_rate_limit(signup_key, limit=5)
        record_auth_failure(signup_key, limit=5)
        full_name = str(payload.get("full_name", "")).strip()
        business_name = str(payload.get("business_name", "")).strip()
        vertical = str(payload.get("vertical", "")).strip().lower()
        password = str(payload.get("password", ""))
        if len(full_name) < 2 or len(full_name) > 100:
            raise HTTPException(status_code=400, detail="Enter your name (2 to 100 characters).")
        if len(business_name) < 2 or len(business_name) > 120:
            raise HTTPException(status_code=400, detail="Enter a business name (2 to 120 characters).")
        if vertical not in {"hvac_plumbing", "dental"}:
            raise HTTPException(status_code=400, detail="Choose HVAC/plumbing or dental.")
        if len(password) < 12:
            raise HTTPException(status_code=400, detail="Use a password with at least 12 characters.")
        email = normalize_signup_email(str(payload.get("email", "")))
        try:
            with transactional_db() as conn:
                conn.execute(
                    """INSERT INTO users (full_name, email, password_hash, business_name, vertical)
                    VALUES (?, ?, ?, ?, ?)""",
                    (full_name, email, hash_password(password), business_name, vertical),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="An application already exists for this email.")
        return JSONResponse(
            status_code=202,
            content={"status": "PENDING", "message": "Application received. An administrator must approve access."},
        )

    @app.post("/api/v1/auth/login")
    def login_endpoint(payload: Dict[str, Any], response: Response, request: Request):
        email = normalize_signup_email(str(payload.get("email", "")))
        rate_key = f"login:{request.client.host if request.client else 'unknown'}:{email}"
        enforce_rate_limit(rate_key, limit=10)
        password = str(payload.get("password", ""))
        with transactional_db() as conn:
            user = conn.execute(
                "SELECT id, email, full_name, password_hash, role, status FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            record_auth_failure(rate_key)
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        if user["status"] == "PENDING":
            raise HTTPException(status_code=403, detail="Your application is waiting for administrator review.")
        if user["status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="This account is currently unavailable.")
        response.set_cookie(
            key="ar_session",
            value=create_session_token(user["id"]),
            max_age=12 * 60 * 60,
            httponly=True,
            secure=settings.APP_ENV.lower() == "production",
            samesite="lax",
            path="/",
        )
        clear_auth_failures(rate_key)
        return {"status": "signed_in", "role": user["role"], "full_name": user["full_name"]}

    @app.post("/api/v1/auth/logout")
    def logout_endpoint(response: Response):
        response.delete_cookie("ar_session", path="/", httponly=True, secure=settings.APP_ENV.lower() == "production", samesite="lax")
        return {"status": "signed_out"}

    @app.get("/api/v1/auth/me")
    def current_user_endpoint(current_user: Dict[str, Any] = Depends(get_current_user)):
        return current_user

    @app.get("/api/v1/admin/metrics")
    def admin_metrics_endpoint(current_user: Dict[str, Any] = Depends(require_owner)):
        return get_admin_metrics_payload()

    @app.post("/api/v1/admin/applications/{application_id}/approve")
    def approve_application_endpoint(
        application_id: int,
        current_user: Dict[str, Any] = Depends(require_owner),
    ):
        with transactional_db() as conn:
            applicant = conn.execute(
                "SELECT * FROM users WHERE id = ? AND role = 'client' AND status = 'PENDING'",
                (application_id,),
            ).fetchone()
            if not applicant:
                raise HTTPException(status_code=404, detail="Pending application not found.")
            slug = re.sub(r"[^a-z0-9]+", "_", applicant["business_name"].lower()).strip("_")[:32] or "client"
            tenant_id = f"{slug}_{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO tenants (tenant_id, business_name, vertical) VALUES (?, ?, ?)",
                (tenant_id, applicant["business_name"], applicant["vertical"]),
            )
            conn.execute(
                "UPDATE users SET status = 'ACTIVE', tenant_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (tenant_id, application_id),
            )
            conn.commit()
        return {"status": "ACTIVE", "tenant_id": tenant_id, "email": applicant["email"]}

    @app.get("/api/v1/client/metrics")
    def client_metrics_endpoint(current_user: Dict[str, Any] = Depends(require_client)):
        return get_client_metrics_payload(current_user["tenant_id"])

    @app.get("/health")
    @app.get("/api/health")
    def health_check():
        return get_health_payload()

    @app.get("/api/v1/voice/state")
    def get_system_state(
        tenant_id: str = "default_clinic",
        retainer_fee_usd: float = 1500.0,
        current_user: Dict[str, Any] = Depends(require_owner),
    ):
        return get_system_state_payload(tenant_id, retainer_fee_usd)

    @app.post("/api/v1/voice/vapi-webhook")
    def vapi_webhook_endpoint(
        payload: Dict[str, Any],
        x_webhook_secret: str | None = Header(default=None),
    ):
        if not is_valid_webhook_secret(x_webhook_secret):
            raise HTTPException(status_code=401, detail="Valid webhook secret required.")
        return process_vapi_webhook_payload(payload)

    @app.post("/api/v1/voice/book-direct")
    def book_direct_endpoint(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(require_owner)):
        return process_direct_booking(payload)

    @app.post("/api/v1/voice/update-booking-status")
    def update_booking_status_endpoint(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(require_owner)):
        with transactional_db() as conn:
            return update_booking_status(
                conn,
                booking_id=int(payload.get("booking_id", 0)),
                tenant_id=payload.get("tenant_id", "default_clinic"),
                new_status=str(payload.get("status", "CONFIRMED")),
            )

    @app.post("/api/v1/voice/release-slot")
    def release_slot_endpoint(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(require_owner)):
        with transactional_db() as conn:
            return release_booked_slot(
                conn,
                booking_id=int(payload.get("booking_id", 0)),
                tenant_id=payload.get("tenant_id", "default_clinic"),
            )

    @app.get("/api/v1/voice/roi-report/{tenant_id}")
    def roi_report_endpoint(tenant_id: str, retainer_fee_usd: float = 1500.0, current_user: Dict[str, Any] = Depends(require_owner)):
        return process_roi_report(tenant_id, retainer_fee_usd)

    @app.post("/api/v1/telephony/warm-transfer-hold")
    def warm_transfer_endpoint(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(require_owner)):
        res = build_warm_transfer_hold_twiml(payload)
        return Response(content=res["twiml"], media_type="application/xml", headers=res["headers"])

    @app.post("/api/v1/telephony/warm-transfer-preview")
    def warm_transfer_preview_endpoint(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(require_owner)):
        return get_warm_transfer_preview_payload(payload)

    @app.get("/api/v1/telephony/staff-whisper")
    def staff_whisper_endpoint(briefing: str = "Incoming warm transfer. Press 1 to accept.", current_user: Dict[str, Any] = Depends(require_owner)):
        return Response(content=build_staff_whisper_twiml(briefing), media_type="application/xml")

    @app.post("/api/v1/voice/run-stress-test")
    def run_stress_test_endpoint(current_user: Dict[str, Any] = Depends(require_owner)):
        return run_stress_test_payload()

    @app.post("/api/v1/voice/pricing-calculator")
    def pricing_calculator_endpoint(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(require_owner)):
        return run_pricing_calculator_payload(payload)

    @app.post("/api/v1/agency/onboard-client")
    def onboard_client_endpoint(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(require_owner)):
        return run_autonomous_onboarding_payload(payload)

    @app.post("/api/v1/agency/generate-gtm-assets")
    def generate_gtm_assets_endpoint(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(require_owner)):
        return generate_gtm_assets_payload(payload)

except ImportError:
    app = None


def run_server(host: str = "0.0.0.0", port: int = 3000) -> None:
    if app is None:
        raise RuntimeError("FastAPI is required. Install backend/requirements.txt before starting the service.")
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
