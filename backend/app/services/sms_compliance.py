import sqlite3
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
    booking_url: str = "https://cal.com/your-clinic/instant-book",
) -> Dict[str, Any]:
    """
    Fires within 10 seconds when an inbound caller hangs up without completing a booking,
    unless the caller is on the TCPA suppression registry.
    """
    if not caller_phone:
        return {"sent": False, "reason": "missing_caller_phone"}

    if is_phone_suppressed(conn, tenant_id, caller_phone):
        return {"sent": False, "reason": "tcpa_suppressed_number"}

    sms_body = (
        f"Hi from {business_name}! Sorry we didn't finish locking in your appointment on the phone. "
        f"You can pick a live time in 15 seconds here: {booking_url} (Reply STOP to opt out)."
    )
    return {
        "sent": True,
        "to": caller_phone,
        "body": sms_body,
    }
