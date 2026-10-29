import json
import uuid
from typing import Dict, Any
from urllib.parse import quote
from xml.sax.saxutils import escape
from django.conf import settings
from apps.core.models import Tenant
from apps.appointments.services import get_open_slots, atomic_book_slot
from apps.compliance.services import (
    detect_tcpa_revocation,
    register_opt_out,
    dispatch_missed_call_sms_fallback,
)
from apps.telemetry.services import record_end_of_call_telemetry


def _tenant_for_call(message: Dict[str, Any], supplied_tenant: str = "") -> str:
    """Bind production traffic to a configured assistant ID; never trust raw model arguments for tenancy."""
    call = message.get("call", {}) or {}
    assistant = message.get("assistant", {}) or {}
    assistant_id = call.get("assistantId") or (assistant.get("id") if isinstance(assistant, dict) else None)
    try:
        mapping = json.loads(settings.VOICE_ASSISTANT_TENANT_MAP_RAW)
    except (TypeError, json.JSONDecodeError):
        mapping = {}
    if assistant_id and assistant_id in mapping:
        return str(mapping[assistant_id])
    if settings.APP_ENV.lower() == "production":
        return ""
    return supplied_tenant


def process_vapi_webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core handler for Vapi / Retell server events:
    - `tool-calls`: Executes `checkCalendar` and `bookAppointment` synchronously and ALWAYS returns
      a flat string inside `results` matching `toolCallId`.
    - `end-of-call-report`: Runs TCPA revocation check, fires missed-call SMS text-back if unbooked,
      and logs ROI telemetry.
    """
    message = payload.get("message", payload)
    message_type = message.get("type", "tool-calls")

    if message_type == "tool-calls":
        tool_calls = message.get("toolCalls") or message.get("toolCallList") or []
        results = []

        for tc in tool_calls:
            tc_id = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")
            fn = tc.get("function", {})
            fn_name = fn.get("name", "")
            args = fn.get("arguments", {})

            tenant_id = _tenant_for_call(message, str(args.get("tenant_id", "")).strip())
            resource_id = str(args.get("resource_id", "")).strip()
            tenant_exists = bool(tenant_id and Tenant.objects.filter(tenant_id=tenant_id).exists())

            if fn_name == "checkCalendar":
                requested_date = str(args.get("requestedDate", ""))
                if not tenant_exists or not resource_id:
                    results.append({"toolCallId": tc_id, "result": "Workspace/resource is not configured. Escalate to staff."})
                    continue
                slots = get_open_slots(tenant_id, resource_id, requested_date, max_options=3)
                slot_str = ", ".join(slots) if slots else "No slots remaining on that date"
                results.append(
                    {
                        "toolCallId": tc_id,
                        "result": f"Available slots for {requested_date}: {slot_str}. Offer 2 options clearly.",
                    }
                )

            elif fn_name == "bookAppointment":
                if not tenant_exists or not resource_id:
                    results.append({"toolCallId": tc_id, "result": "Workspace/resource is not configured. Escalate to staff."})
                    continue
                workflow_run_id = args.get("workflow_run_id") or tc_id
                first_name = str(args.get("firstName", "")).strip()
                phone = str(args.get("phone", "")).strip()
                service_type = str(args.get("serviceType", "")).strip()
                requested_time = str(args.get("requestedTime", "")).strip()
                verbal_confirmed = bool(args.get("verbalConfirmationConfirmed", False))
                if not (first_name and phone and service_type and requested_time):
                    results.append({"toolCallId": tc_id, "result": "Required booking details are missing. Collect them before confirming."})
                    continue

                outcome = atomic_book_slot(
                    tenant_id=tenant_id,
                    resource_id=resource_id,
                    slot_iso=requested_time,
                    idempotency_key=f"{tenant_id}:{workflow_run_id}:{requested_time}",
                    caller_name=first_name,
                    caller_phone=phone,
                    service_type=service_type,
                    verbal_confirmed=verbal_confirmed,
                )
                results.append({"toolCallId": tc_id, "result": outcome["message"]})

            else:
                results.append({"toolCallId": tc_id, "result": f"Function {fn_name} is not handled by this middleware."})

        return {"results": results}

    elif message_type in ("end-of-call-report", "call-ended"):
        call_obj = message.get("call", {})
        call_id = call_obj.get("id") or message.get("call_id") or f"call_{uuid.uuid4().hex[:10]}"
        customer_obj = call_obj.get("customer", {})
        customer_phone = customer_obj.get("number") or message.get("caller_number") or ""
        supplied_tenant = str(call_obj.get("tenantId") or message.get("tenant_id") or "default_clinic").strip()
        tenant_id = _tenant_for_call(message, supplied_tenant) or "default_clinic"

        duration = float(message.get("durationSeconds") or message.get("duration") or 0.0)
        cost = float(message.get("cost") or 0.0)
        p50 = int(message.get("turnLatencyP50Ms") or 535)
        p95 = int(message.get("turnLatencyP95Ms") or 710)
        ttfa = int(message.get("ttfaMs") or 120)

        transcript = str(message.get("transcript") or "")
        analysis = message.get("analysis", {})
        structured = analysis.get("structuredData", {})
        summary = str(analysis.get("summary") or transcript[:400])

        appointment_booked = bool(structured.get("appointmentBooked", False))
        human_transferred = bool(structured.get("transferredToHuman", False))
        is_after_hours = bool(structured.get("isAfterHours", False))

        opt_out_detected = detect_tcpa_revocation(transcript)
        if opt_out_detected and customer_phone:
            register_opt_out(
                tenant_id=tenant_id,
                phone_number=customer_phone,
                revocation_phrase=opt_out_detected,
                channel="voice",
            )

        sms_result = None
        if not appointment_booked and not human_transferred and customer_phone:
            tenant_obj = Tenant.objects.filter(tenant_id=tenant_id).first()
            sms_result = dispatch_missed_call_sms_fallback(
                tenant_id=tenant_id,
                caller_phone=customer_phone,
                business_name=tenant_obj.business_name if tenant_obj else "Our Practice",
                booking_url=f"https://cal.com/{tenant_id}/instant-book",
                consented=bool(structured.get("smsConsentGiven", False)),
            )

        telemetry = record_end_of_call_telemetry(
            call_id=call_id,
            tenant_id=tenant_id,
            caller_phone=customer_phone,
            duration_seconds=duration,
            cost_usd=cost,
            appointment_booked=appointment_booked,
            human_transferred=human_transferred,
            after_hours=is_after_hours,
            summary=summary,
            turn_latency_p50_ms=p50,
            turn_latency_p95_ms=p95,
            ttfa_ms=ttfa,
        )

        return {
            "status": "PROCESSED",
            "call_id": call_id,
            "tenant_id": tenant_id,
            "appointment_booked": appointment_booked,
            "opt_out_registered": bool(opt_out_detected),
            "sms_fallback": sms_result,
            "telemetry": telemetry,
        }

    return {"status": "IGNORED", "message_type": message_type}


def build_warm_transfer_hold_twiml(payload: Dict[str, Any]) -> Dict[str, Any]:
    caller_phone = str(payload.get("caller_phone", "+15550000000"))
    caller_name = escape(str(payload.get("caller_name", "Caller"))[:100])
    urgency_reason = escape(str(payload.get("urgency_reason", "Urgent inquiry"))[:300])
    verified_details = escape(str(payload.get("verified_details", "Standard intake completed"))[:500])

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


def build_staff_whisper_twiml(briefing: str = "Incoming warm transfer from AI receptionist. Press 1 to accept.") -> str:
    briefing = escape(str(briefing)[:1000])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="1" timeout="8">
        <Say voice="Polly.Joanna-Neural">{briefing}</Say>
    </Gather>
</Response>"""


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

