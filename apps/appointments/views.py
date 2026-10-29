import json
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from apps.appointments.services import (
    atomic_book_slot,
    release_booked_slot,
    update_booking_status,
)


def _json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        return {}


@csrf_exempt
def book_direct_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    tenant_id = str(payload.get("tenant_id", "default_clinic")).strip()
    resource_id = str(payload.get("resource_id", "chair_1")).strip()
    workflow_run_id = str(payload.get("workflow_run_id", "direct_run"))
    first_name = str(payload.get("firstName", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    service_type = str(payload.get("serviceType", "consultation")).strip()
    requested_time = str(payload.get("requestedTime", "")).strip()
    verbal_confirmed = bool(payload.get("verbalConfirmationConfirmed", True))

    idempotency_key = f"{tenant_id}:{workflow_run_id}:{requested_time}"
    result = atomic_book_slot(
        tenant_id=tenant_id,
        resource_id=resource_id,
        slot_iso=requested_time,
        idempotency_key=idempotency_key,
        caller_name=first_name,
        caller_phone=phone,
        service_type=service_type,
        verbal_confirmed=verbal_confirmed,
    )
    return JsonResponse(result)


@csrf_exempt
def update_booking_status_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    booking_id = int(payload.get("booking_id", 0))
    tenant_id = str(payload.get("tenant_id", "default_clinic"))
    new_status = str(payload.get("status", "CONFIRMED"))
    result = update_booking_status(booking_id, tenant_id, new_status)
    return JsonResponse(result)


@csrf_exempt
def release_slot_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    booking_id = int(payload.get("booking_id", 0))
    tenant_id = str(payload.get("tenant_id", "default_clinic"))
    result = release_booked_slot(booking_id, tenant_id)
    return JsonResponse(result)

