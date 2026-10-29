import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.database import init_db, transactional_db
from app.api.voice_webhooks import (
    process_vapi_webhook_payload,
    process_direct_booking,
    process_roi_report,
)
from app.api.twilio_transfer import (
    build_warm_transfer_hold_twiml,
    build_staff_whisper_twiml,
)

init_db()


def _seed_initial_demo_data_if_empty() -> None:
    with transactional_db() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM appointment_slot_locks").fetchone()["c"]
        if count == 0:
            process_direct_booking(
                {
                    "tenant_id": "default_clinic",
                    "resource_id": "chair_1",
                    "workflow_run_id": "seed_run_001",
                    "firstName": "Sarah Jenkins",
                    "phone": "+15552223333",
                    "serviceType": "implant_consultation",
                    "requestedTime": "2026-11-05T10:00:00",
                }
            )
            process_direct_booking(
                {
                    "tenant_id": "default_clinic",
                    "resource_id": "chair_1",
                    "workflow_run_id": "seed_run_002",
                    "firstName": "Marcus Vance",
                    "phone": "+15553334444",
                    "serviceType": "emergency_crown_repair",
                    "requestedTime": "2026-11-05T14:00:00",
                }
            )
            process_vapi_webhook_payload(
                {
                    "message": {
                        "type": "end-of-call-report",
                        "durationSeconds": 118.0,
                        "cost": 0.16,
                        "call": {
                            "id": "call_seed_101",
                            "tenantId": "default_clinic",
                            "customer": {"number": "+15552223333"},
                        },
                        "transcript": "Caller booked an implant consultation for 10:00 AM.",
                        "analysis": {
                            "summary": "Booked implant consultation for Sarah Jenkins (Chair 1).",
                            "structuredData": {
                                "appointmentBooked": True,
                                "transferredToHuman": False,
                                "isAfterHours": True,
                            },
                        },
                    }
                }
            )
            process_vapi_webhook_payload(
                {
                    "message": {
                        "type": "end-of-call-report",
                        "durationSeconds": 94.0,
                        "cost": 0.13,
                        "call": {
                            "id": "call_seed_102",
                            "tenantId": "default_clinic",
                            "customer": {"number": "+15553334444"},
                        },
                        "transcript": "Caller booked emergency crown repair at 2:00 PM.",
                        "analysis": {
                            "summary": "Booked emergency crown repair for Marcus Vance.",
                            "structuredData": {
                                "appointmentBooked": True,
                                "transferredToHuman": False,
                                "isAfterHours": False,
                            },
                        },
                    }
                }
            )


_seed_initial_demo_data_if_empty()

# FastAPI wiring when running in full container/ASGI environment
try:
    from fastapi import FastAPI, Response
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(
        title="AI Voice Receptionist Enterprise Middleware",
        description=(
            "Atomic Calendar Slot-Locking, Vapi/Retell Tool Router, "
            "Contextual Twilio Warm-Transfer Whisper Bridge, and TCPA Revocation Engine."
        ),
        version="1.0.0",
    )

    STATIC_DIR = ROOT_DIR / "static"
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def root_dashboard():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse("<h1>AI Voice Receptionist Enterprise Middleware</h1><p>Visit <a href='/docs'>/docs</a> or <a href='/health'>/health</a>.</p>")

    @app.get("/health")
    @app.get("/api/health")
    def health_check():
        return {
            "status": "healthy",
            "service": "ai-voice-receptionist-enterprise",
            "features": [
                "atomic_slot_locking",
                "idempotent_tool_retries",
                "warm_transfer_whisper",
                "tcpa_april_2025_revocation",
                "automated_roi_telemetry",
            ],
        }

    @app.get("/api/v1/voice/state")
    def get_system_state(tenant_id: str = "default_clinic", retainer_fee_usd: float = 1500.0):
        with transactional_db() as conn:
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
                    "SELECT * FROM call_telemetry_logs WHERE tenant_id = ? ORDER BY id DESC LIMIT 20",
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
        roi = process_roi_report(tenant_id, retainer_fee_usd)
        return {
            "tenant_id": tenant_id,
            "bookings": bookings,
            "calls": calls,
            "suppressions": suppressions,
            "roi": roi,
        }

    @app.post("/api/v1/voice/vapi-webhook")
    def vapi_webhook_endpoint(payload: Dict[str, Any]):
        return process_vapi_webhook_payload(payload)

    @app.post("/api/v1/voice/book-direct")
    def book_direct_endpoint(payload: Dict[str, Any]):
        return process_direct_booking(payload)

    @app.get("/api/v1/voice/roi-report/{tenant_id}")
    def roi_report_endpoint(tenant_id: str, retainer_fee_usd: float = 1500.0):
        return process_roi_report(tenant_id, retainer_fee_usd)

    @app.post("/api/v1/telephony/warm-transfer-hold")
    def warm_transfer_endpoint(payload: Dict[str, Any]):
        res = build_warm_transfer_hold_twiml(payload)
        return Response(content=res["twiml"], media_type="application/xml", headers=res["headers"])

    @app.post("/api/v1/telephony/warm-transfer-preview")
    def warm_transfer_preview_endpoint(payload: Dict[str, Any]):
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

    @app.get("/api/v1/telephony/staff-whisper")
    def staff_whisper_endpoint(briefing: str = "Incoming warm transfer. Press 1 to accept."):
        return Response(content=build_staff_whisper_twiml(briefing), media_type="application/xml")

    @app.post("/api/v1/voice/run-stress-test")
    def run_stress_test_endpoint():
        from stress_test_simulator import run_verification_suite

        buf = io.StringIO()
        with redirect_stdout(buf):
            run_verification_suite()
        return {"status": "passed", "output": buf.getvalue()}

    @app.post("/api/v1/voice/pricing-calculator")
    def pricing_calculator_endpoint(payload: Dict[str, Any]):
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

except ImportError:
    app = None


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)
