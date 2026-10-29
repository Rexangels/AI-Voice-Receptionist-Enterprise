import uuid
import json
from typing import Dict, Any
from app.database import transactional_db
from app.services.slot_locker import get_open_slots, atomic_book_slot
from app.services.sms_compliance import (
    detect_tcpa_revocation,
    register_opt_out,
    dispatch_missed_call_sms_fallback,
)
from app.services.crm_sync import record_end_of_call_telemetry, generate_monthly_roi_report
from app.config import settings


def _tenant_for_call(message: Dict[str, Any], supplied_tenant: str = "") -> str:
    """Bind production traffic to a configured assistant ID; never trust model arguments for tenancy."""
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


def process_vapi_webhook_payload(payload: Dict[str, Any], db_path: str | None = None) -> Dict[str, Any]:
    """
    Core handler for Vapi / Retell server events:
    - `tool-calls`: Executes `checkCalendar` and `bookAppointment` synchronously and ALWAYS returns
      a flat string inside `results` matching `toolCallId`.
    - `end-of-call-report`: Runs TCPA revocation check, fires missed-call SMS text-back if unbooked,
      and logs ROI telemetry.
    """
    message = payload.get("message", payload)
    message_type = message.get("type", "tool-calls")

    with transactional_db(db_path) as conn:
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
                tenant_exists = bool(tenant_id and conn.execute(
                    "SELECT 1 FROM tenants WHERE tenant_id = ?", (tenant_id,)
                ).fetchone())

                if fn_name == "checkCalendar":
                    requested_date = str(args.get("requestedDate", ""))
                    if not tenant_exists or not resource_id:
                        results.append({"toolCallId": tc_id, "result": "Workspace/resource is not configured. Escalate to staff."})
                        continue
                    slots = get_open_slots(conn, tenant_id, resource_id, requested_date, max_options=3)
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
                        conn=conn,
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
                    results.append(
                        {"toolCallId": tc_id, "result": f"Unsupported tool: {fn_name}. Escalate to staff."}
                    )

            return {"results": results}

        if message_type == "end-of-call-report":
            call_obj = message.get("call", {})
            call_id = str(call_obj.get("id", "")).strip()
            tenant_id = _tenant_for_call(message, str(call_obj.get("tenantId", "")).strip())
            customer_phone = str(call_obj.get("customer", {}).get("number", "")).strip()
            if not call_id or not tenant_id or not customer_phone or not conn.execute(
                "SELECT 1 FROM tenants WHERE tenant_id = ?", (tenant_id,)
            ).fetchone():
                return {"status": "rejected", "reason": "call_tenant_or_caller_identity_missing"}
            existing_call = conn.execute(
                "SELECT attributed_revenue_usd FROM call_telemetry_logs WHERE call_id = ? AND tenant_id = ?",
                (call_id, tenant_id),
            ).fetchone()
            if existing_call:
                return {
                    "status": "duplicate_ignored",
                    "call_id": call_id,
                    "attributed_revenue_usd": existing_call["attributed_revenue_usd"],
                }
            transcript = message.get("transcript", "")
            analysis = message.get("analysis", {})
            summary = analysis.get("summary", "Call completed.")
            structured = analysis.get("structuredData", {})
            appointment_booked = bool(structured.get("appointmentBooked", False))
            human_transferred = bool(structured.get("transferredToHuman", False))
            transcript_lower = str(transcript).lower()
            consent_evidence = (
                "yes, you can text me" in transcript_lower
                or "yes, you may text me" in transcript_lower
                or "i agree to receive text messages" in transcript_lower
            )
            # Structured model output alone is not evidence of permission to text.
            sms_consent = bool(structured.get("smsConsent", False)) and consent_evidence
            after_hours = bool(structured.get("isAfterHours", False))
            duration_seconds = float(message.get("durationSeconds", 0.0))
            cost_usd = float(message.get("cost", 0.0))
            p50_ms = int(message.get("turnLatencyP50Ms", 0))
            p95_ms = int(message.get("turnLatencyP95Ms", 0))
            ttfa_ms = int(message.get("ttfaMs", 0))

            revoked_phrase = detect_tcpa_revocation(transcript)
            tcpa_action = None
            if revoked_phrase:
                tcpa_action = register_opt_out(
                    conn=conn,
                    tenant_id=tenant_id,
                    phone_number=customer_phone,
                    revocation_phrase=revoked_phrase,
                    channel="voice",
                )

            sms_fallback = None
            if not appointment_booked and not human_transferred and not revoked_phrase:
                tenant_row = conn.execute(
                    "SELECT business_name FROM tenants WHERE tenant_id = ?", (tenant_id,)
                ).fetchone()
                biz_name = tenant_row["business_name"] if tenant_row else "Our Practice"
                sms_fallback = dispatch_missed_call_sms_fallback(
                    conn=conn,
                    tenant_id=tenant_id,
                    caller_phone=customer_phone,
                    business_name=biz_name,
                    consented=sms_consent,
                )

            telemetry = record_end_of_call_telemetry(
                conn=conn,
                call_id=call_id,
                tenant_id=tenant_id,
                caller_phone=customer_phone,
                duration_seconds=duration_seconds,
                cost_usd=cost_usd,
                appointment_booked=appointment_booked,
                human_transferred=human_transferred,
                after_hours=after_hours,
                summary=summary,
                turn_latency_p50_ms=p50_ms,
                turn_latency_p95_ms=p95_ms,
                ttfa_ms=ttfa_ms,
            )

            return {
                "status": "processed",
                "call_id": telemetry["call_id"],
                "attributed_revenue_usd": telemetry["attributed_revenue_usd"],
                "tcpa_revocation": tcpa_action,
                "missed_call_sms_fallback": sms_fallback,
            }

    return {"status": "ignored", "type": message_type}


def process_direct_booking(payload: Dict[str, Any], db_path: str | None = None) -> Dict[str, Any]:
    tenant_id = payload.get("tenant_id", "default_clinic")
    resource_id = payload.get("resource_id", "chair_1")
    workflow_run_id = payload["workflow_run_id"]
    requested_time = payload["requestedTime"]
    verbal_confirmed = bool(payload.get("verbalConfirmationConfirmed", True))

    with transactional_db(db_path) as conn:
        return atomic_book_slot(
            conn=conn,
            tenant_id=tenant_id,
            resource_id=resource_id,
            slot_iso=requested_time,
            idempotency_key=f"{tenant_id}:{workflow_run_id}:{requested_time}",
            caller_name=payload["firstName"],
            caller_phone=payload["phone"],
            service_type=payload["serviceType"],
            verbal_confirmed=verbal_confirmed,
        )


def process_roi_report(
    tenant_id: str, retainer_fee_usd: float = 1500.0, db_path: str | None = None
) -> Dict[str, Any]:
    with transactional_db(db_path) as conn:
        return generate_monthly_roi_report(conn, tenant_id=tenant_id, retainer_fee_usd=retainer_fee_usd)
