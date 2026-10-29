import hmac
import json
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from apps.voice_telephony.services import (
    process_vapi_webhook_payload,
    build_warm_transfer_hold_twiml,
    build_staff_whisper_twiml,
    get_warm_transfer_preview_payload,
)


def _json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        return {}


def _is_valid_webhook_secret(value: str | None) -> bool:
    if not settings.WEBHOOK_SECRET:
        return True
    return bool(value and hmac.compare_digest(value, settings.WEBHOOK_SECRET))


@csrf_exempt
def vapi_webhook_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    secret_header = request.headers.get("X-Webhook-Secret")
    if not _is_valid_webhook_secret(secret_header):
        return JsonResponse({"detail": "Valid webhook secret required."}, status=401)
    payload = _json_body(request)
    result = process_vapi_webhook_payload(payload)
    return JsonResponse(result)


@csrf_exempt
def warm_transfer_hold_endpoint(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)
    payload = _json_body(request)
    res = build_warm_transfer_hold_twiml(payload)
    response = HttpResponse(res["twiml"], content_type="application/xml; charset=utf-8")
    for k, v in res.get("headers", {}).items():
        response[k] = v
    return response


def staff_whisper_endpoint(request: HttpRequest) -> HttpResponse:
    briefing = request.GET.get("briefing", "Incoming warm transfer. Press 1 to accept.")
    twiml = build_staff_whisper_twiml(briefing)
    return HttpResponse(twiml, content_type="application/xml; charset=utf-8")


@csrf_exempt
def warm_transfer_preview_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    preview = get_warm_transfer_preview_payload(payload)
    return JsonResponse(preview)

