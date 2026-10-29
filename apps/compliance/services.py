import base64
import re
from typing import Dict, Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from django.conf import settings
from apps.core.models import Tenant
from apps.compliance.models import SuppressionRegistry

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
    Implements FCC April 11, 2025 Enhanced TCPA Revocation Rule:
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
    tenant_id: str,
    phone_number: str,
    revocation_phrase: str,
    channel: str = "voice",
) -> Dict[str, Any]:
    tenant = Tenant.objects.filter(tenant_id=tenant_id).first()
    if not tenant:
        return {"suppressed": False, "error": f"Tenant '{tenant_id}' not found."}

    obj, created = SuppressionRegistry.objects.get_or_create(
        tenant=tenant,
        phone_number=phone_number,
        defaults={"revocation_phrase": revocation_phrase, "channel": channel},
    )
    if not created and obj.revocation_phrase != revocation_phrase:
        obj.revocation_phrase = revocation_phrase
        obj.save(update_fields=["revocation_phrase"])

    return {
        "suppressed": True,
        "phone_number": phone_number,
        "phrase": revocation_phrase,
        "already_listed": not created,
    }


def is_phone_suppressed(tenant_id: str, phone_number: str) -> bool:
    return SuppressionRegistry.objects.filter(tenant_id=tenant_id, phone_number=phone_number).exists()


def dispatch_missed_call_sms_fallback(
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

    if is_phone_suppressed(tenant_id, caller_phone):
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
    payload = urlencode({
        "To": caller_phone,
        "From": settings.TWILIO_PHONE_NUMBER,
        "Body": sms_body,
    }).encode()
    request = Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urlopen(request, timeout=5.0) as response:
            return {"sent": response.status in (200, 201), "status_code": response.status, "body": sms_body}
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"sent": False, "reason": "upstream_sms_delivery_failed", "error": str(exc)}

