from urllib.parse import quote
from typing import Dict, Any
from app.config import settings


def build_warm_transfer_hold_twiml(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the Twilio Conference TwiML and Whisper headers so the caller is placed on brief hold
    while the AI whispers a 10-second context summary to the human staff member.
    """
    caller_name = payload.get("caller_name", "Caller")
    caller_phone = payload.get("caller_phone", "+15550000000")
    urgency_reason = payload.get("urgency_reason", "Urgent inquiry")
    verified_details = payload.get("verified_details", "Standard intake completed")

    conf_room = f"TransferRoom_{caller_phone.replace('+', '')}"
    whisper_query = quote(
        f"Incoming AI Receptionist warm transfer. Caller {caller_name} on line regarding "
        f"{urgency_reason}. {verified_details}. Press 1 to connect immediately."
    )
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">Please hold for just a moment while I brief our team and connect you directly.</Say>
    <Dial>
        <Conference startConferenceOnEnter="true" endConferenceOnExit="false">{conf_room}</Conference>
    </Dial>
</Response>"""
    return {
        "twiml": twiml,
        "headers": {
            "X-Conference-Room": conf_room,
            "X-Staff-Destination": settings.HUMAN_ESCALATION_NUMBER,
            "X-Whisper-Url": f"/api/v1/telephony/staff-whisper?briefing={whisper_query}",
        },
    }


def build_staff_whisper_twiml(
    briefing: str = "Incoming warm transfer from AI receptionist. Press 1 to accept.",
) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="1" timeout="8">
        <Say voice="Polly.Joanna-Neural">{briefing}</Say>
    </Gather>
</Response>"""
