import sqlite3
import base64
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from app.config import settings
from typing import Dict, Any

OPT_OUT_PHRASES = [
    "stop",
    "unsubscribe",
    "cancel",
    "quit",
    "remove me",
    "do not call",
    "don't call me",
    "take me off your list",
    "opt out",
]


def detect_tcpa_revocation(transcript_text: str) -> str | None:
    """
    Implements the FCC April 11, 2025 Enhanced TCPA Revocation Rule:
    Detects natural-language consent revocation alongside standard STOP keywords.
    """
    if not transcript_text:
        return None
    lowered = transcript_text.lower()
    for phrase in OPT_OUT_PHRASES:
        if phrase in lowered:
            return phrase
    return None


def register_opt_out(
    conn: sqlite3.Connection,
    tenant_id: str,
    phone_number: str,
    revocation_phrase: str,
    channel: str = "voice",
) -> Dict[str, Any]:
    try:
        conn.execute(
            """
            INSERT INTO suppression_registry (tenant_id, phone_number, revocation_phrase, channel)
            VALUES (?, ?, ?, ?)
            """,
            (tenant_id, phone_number, revocation_phrase, channel),
        )
        conn.commit()
        return {"suppressed": True, "phone_number": phone_number, "phrase": revocation_phrase}
    except sqlite3.IntegrityError:
        conn.rollback()
        return {"suppressed": True, "phone_number": phone_number, "already_listed": True}


def is_phone_suppressed(conn: sqlite3.Connection, tenant_id: str, phone_number: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM suppression_registry WHERE tenant_id = ? AND phone_number = ?",
        (tenant_id, phone_number),
    )
    return cur.fetchone() is not None


def dispatch_missed_call_sms_fallback(
    conn: sqlite3.Connection,
    tenant_id: str,
    caller_phone: str,
    business_name: str = "Our Practice",
    booking_url: str = "",
    consented: bool = False,
) -> Dict[str, Any]:
    """
    Fires within 10 seconds when an inbound caller hangs up without completing a booking,
    unless the caller is on the TCPA suppression registry.
    """
    if not caller_phone:
        return {"sent": False, "reason": "missing_caller_phone"}

    if is_phone_suppressed(conn, tenant_id, caller_phone):
        return {"sent": False, "reason": "tcpa_suppressed_number"}
    if not consented:
        return {"sent": False, "reason": "documented_sms_consent_required"}
    if not booking_url or "your-clinic" in booking_url:
        return {"sent": False, "reason": "tenant_booking_url_not_configured"}

    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER):
        return {"sent": False, "reason": "twilio_not_configured"}
    if not re.fullmatch(r"\+[1-9]\d{7,14}", caller_phone):
        return {"sent": False, "reason": "invalid_destination_number"}
    sms_body = (
        f"Hi from {business_name}! Sorry we didn't finish your appointment request. "
        f"You can choose a time here: {booking_url} (Reply STOP to opt out)."
    )[:1500]
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    auth = base64.b64encode(f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}".encode()).decode()
    request = Request(
        endpoint,
        data=urlencode({"To": caller_phone, "From": settings.TWILIO_PHONE_NUMBER, "Body": sms_body}).encode(),
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            import json
            result = json.loads(response.read().decode("utf-8"))
        return {"sent": True, "to": caller_phone, "message_sid": result.get("sid"), "status": result.get("status")}
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        # Never claim delivery when the provider did not accept the request.
        return {"sent": False, "reason": "twilio_request_failed"}
