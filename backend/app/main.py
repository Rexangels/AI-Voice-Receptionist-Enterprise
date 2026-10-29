from typing import Dict, Any
from app.database import init_db
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

# FastAPI wiring when running in full container/ASGI environment
try:
    from fastapi import FastAPI, Response

    app = FastAPI(
        title="AI Voice Receptionist Enterprise Middleware",
        description=(
            "Atomic Calendar Slot-Locking, Vapi/Retell Tool Router, "
            "Contextual Twilio Warm-Transfer Whisper Bridge, and TCPA Revocation Engine."
        ),
        version="1.0.0",
    )

    @app.get("/health")
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

    @app.get("/api/v1/telephony/staff-whisper")
    def staff_whisper_endpoint(briefing: str = "Incoming warm transfer. Press 1 to accept."):
        return Response(content=build_staff_whisper_twiml(briefing), media_type="application/xml")

except ImportError:
    app = None
