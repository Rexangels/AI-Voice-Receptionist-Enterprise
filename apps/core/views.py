import json
import re
import uuid
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse, HttpResponse, FileResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, Sum, Q
from apps.core.models import User, Tenant
from apps.telemetry.models import CallTelemetryLog
from apps.appointments.models import AppointmentSlotLock


def _json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        return {}


def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({
        "status": "healthy",
        "service": "ai-voice-receptionist-enterprise",
        "framework": "Django 5.2",
        "commercial_readiness": "PROTOTYPE",
        "features": [
            "django_orm_concurrency_locks",
            "django_admin_backoffice",
            "atomic_slot_locking",
            "idempotent_tool_retries",
            "verbal_confirmation_gate",
            "warm_transfer_whisper",
            "tcpa_april_2025_revocation",
            "automated_roi_telemetry",
            "autonomous_5_stage_onboarding",
            "minute_overage_guardrails",
        ],
    })


# HTML Frontend Page Views
def index_page(request: HttpRequest):
    index_file = settings.BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(open(index_file, "rb"), content_type="text/html; charset=utf-8")
    return HttpResponse("<h1>AI Voice Receptionist Enterprise</h1>")


def login_page(request: HttpRequest):
    login_file = settings.BASE_DIR / "static" / "login.html"
    if login_file.exists():
        return FileResponse(open(login_file, "rb"), content_type="text/html; charset=utf-8")
    return HttpResponse("<h1>Sign in</h1>")


def signup_page(request: HttpRequest):
    signup_file = settings.BASE_DIR / "static" / "signup.html"
    if signup_file.exists():
        return FileResponse(open(signup_file, "rb"), content_type="text/html; charset=utf-8")
    return HttpResponse("<h1>Request a workspace</h1>")


def admin_page(request: HttpRequest):
    admin_file = settings.BASE_DIR / "static" / "admin.html"
    if admin_file.exists():
        return FileResponse(open(admin_file, "rb"), content_type="text/html; charset=utf-8")
    return HttpResponse("<h1>Agency admin</h1>")


def client_page(request: HttpRequest):
    client_file = settings.BASE_DIR / "static" / "client.html"
    if client_file.exists():
        return FileResponse(open(client_file, "rb"), content_type="text/html; charset=utf-8")
    return HttpResponse("<h1>Client workspace</h1>")


def public_asset(request: HttpRequest, path: str):
    target = (settings.PUBLIC_DIR / path).resolve()
    if str(target).startswith(str(settings.PUBLIC_DIR.resolve())) and target.is_file():
        ctype = "application/pdf" if target.suffix.lower() == ".pdf" else "application/octet-stream"
        return FileResponse(open(target, "rb"), content_type=ctype)
    return HttpResponse("Asset not found", status=404)


# Auth Endpoints
@csrf_exempt
def signup_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    full_name = str(payload.get("full_name", "")).strip()
    business_name = str(payload.get("business_name", "")).strip()
    vertical = str(payload.get("vertical", "")).strip().lower()
    password = str(payload.get("password", ""))
    email = str(payload.get("email", "")).strip().lower()

    if len(full_name) < 2 or len(full_name) > 100:
        return JsonResponse({"detail": "Enter your name (2 to 100 characters)."}, status=400)
    if len(business_name) < 2 or len(business_name) > 120:
        return JsonResponse({"detail": "Enter a business name (2 to 120 characters)."}, status=400)
    if vertical not in {"hvac_plumbing", "dental"}:
        return JsonResponse({"detail": "Choose HVAC/plumbing or dental."}, status=400)
    if len(password) < 12:
        return JsonResponse({"detail": "Use a password with at least 12 characters."}, status=400)
    if "@" not in email or "." not in email:
        return JsonResponse({"detail": "Enter a valid email address."}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"detail": "An application already exists for this email."}, status=409)

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        business_name=business_name,
        vertical=vertical,
        role="client",
        status="PENDING",
    )

    return JsonResponse(
        {"status": "PENDING", "message": "Application received. An administrator must approve access."},
        status=202,
    )


@csrf_exempt
def login_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = _json_body(request)
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    user = User.objects.filter(email=email).first()
    if not user or not user.check_password(password):
        return JsonResponse({"detail": "Email or password is incorrect."}, status=401)
    if user.status == "PENDING":
        return JsonResponse({"detail": "Your application is waiting for administrator review."}, status=403)
    if user.status != "ACTIVE":
        return JsonResponse({"detail": "This account is currently unavailable."}, status=403)

    login(request, user)
    return JsonResponse({
        "status": "signed_in",
        "role": user.role,
        "full_name": user.full_name,
    })


@csrf_exempt
def logout_endpoint(request: HttpRequest) -> JsonResponse:
    logout(request)
    return JsonResponse({"status": "signed_out"})


def current_user_endpoint(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated"}, status=401)
    user = request.user
    return JsonResponse({
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "status": user.status,
        "tenant_id": user.tenant_id,
        "business_name": user.business_name,
        "vertical": user.vertical,
    })


# Admin Endpoints
def admin_metrics_endpoint(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated or request.user.role != "owner":
        return JsonResponse({"detail": "Owner access required."}, status=403)

    client_count = Tenant.objects.count()
    active_accounts = User.objects.filter(role="client", status="ACTIVE").count()
    pending_applications = User.objects.filter(role="client", status="PENDING").count()

    call_agg = CallTelemetryLog.objects.aggregate(
        total_calls=Count("id"),
        booked_calls=Count("id", filter=Q(appointment_booked=True)),
        transfers=Count("id", filter=Q(human_transferred=True)),
        after_hours_calls=Count("id", filter=Q(after_hours=True)),
        race_conflicts_prevented=Count("id", filter=Q(race_conflict_prevented=True)),
        estimated_voice_cost=Sum("cost_usd"),
        attributed_revenue=Sum("attributed_revenue_usd"),
        avg_turn_latency_p50=Sum("turn_latency_p50_ms"),
        avg_turn_latency_p95=Sum("turn_latency_p95_ms"),
        avg_ttfa=Sum("ttfa_ms"),
    )

    total_calls = call_agg["total_calls"] or 0
    booked_calls = call_agg["booked_calls"] or 0
    booking_rate = round(booked_calls / total_calls, 4) if total_calls else 0.0

    totals = {
        "client_count": client_count,
        "active_accounts": active_accounts,
        "pending_applications": pending_applications,
        "total_calls": total_calls,
        "booked_calls": booked_calls,
        "booking_rate": booking_rate,
        "transfers": call_agg["transfers"] or 0,
        "after_hours_calls": call_agg["after_hours_calls"] or 0,
        "race_conflicts_prevented": call_agg["race_conflicts_prevented"] or 0,
        "opt_outs_recorded": 0,
        "estimated_voice_cost_usd": round(call_agg["estimated_voice_cost"] or 0.0, 2),
        "attributed_revenue_usd": round(call_agg["attributed_revenue"] or 0.0, 2),
        "avg_turn_latency_p50_ms": int((call_agg["avg_turn_latency_p50"] or 540) / (total_calls or 1)),
        "avg_turn_latency_p95_ms": int((call_agg["avg_turn_latency_p95"] or 720) / (total_calls or 1)),
        "avg_ttfa_ms": int((call_agg["avg_ttfa"] or 125) / (total_calls or 1)),
    }

    clients = []
    for t in Tenant.objects.all():
        t_calls = CallTelemetryLog.objects.filter(tenant=t).aggregate(
            total_calls=Count("id"),
            booked_calls=Count("id", filter=Q(appointment_booked=True)),
            transfers=Count("id", filter=Q(human_transferred=True)),
            cost=Sum("cost_usd"),
            rev=Sum("attributed_revenue_usd"),
        )
        clients.append({
            "tenant_id": t.tenant_id,
            "business_name": t.business_name,
            "vertical": t.vertical,
            "created_at": t.created_at.strftime("%Y-%m-%d"),
            "total_calls": t_calls["total_calls"] or 0,
            "booked_calls": t_calls["booked_calls"] or 0,
            "transfers": t_calls["transfers"] or 0,
            "estimated_voice_cost_usd": round(t_calls["cost"] or 0.0, 2),
            "attributed_revenue_usd": round(t_calls["rev"] or 0.0, 2),
        })

    applications = [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "business_name": u.business_name,
            "vertical": u.vertical,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for u in User.objects.filter(role="client", status="PENDING").order_by("created_at")[:100]
    ]

    return JsonResponse({
        "environment": settings.APP_ENV,
        "metrics": totals,
        "clients": clients,
        "applications": applications,
    })


@csrf_exempt
def approve_application_endpoint(request: HttpRequest, application_id: int) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    if not request.user.is_authenticated or request.user.role != "owner":
        return JsonResponse({"detail": "Owner access required."}, status=403)

    applicant = User.objects.filter(id=application_id, role="client", status="PENDING").first()
    if not applicant:
        return JsonResponse({"detail": "Pending application not found."}, status=404)

    slug = re.sub(r"[^a-z0-9]+", "_", applicant.business_name.lower()).strip("_")[:32] or "client"
    tenant_id = f"{slug}_{uuid.uuid4().hex[:8]}"

    tenant = Tenant.objects.create(
        tenant_id=tenant_id,
        business_name=applicant.business_name,
        vertical=applicant.vertical,
    )
    applicant.status = "ACTIVE"
    applicant.tenant = tenant
    applicant.save(update_fields=["status", "tenant", "updated_at"])

    return JsonResponse({"status": "ACTIVE", "tenant_id": tenant_id, "email": applicant.email})


# Client Metrics Endpoint
def client_metrics_endpoint(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated or request.user.role != "client":
        return JsonResponse({"detail": "Client access required."}, status=403)

    tenant = request.user.tenant
    if not tenant:
        return JsonResponse({"tenant": None, "metrics": {}, "calls": [], "bookings": []})

    call_agg = CallTelemetryLog.objects.filter(tenant=tenant).aggregate(
        total_calls=Count("id"),
        booked_calls=Count("id", filter=Q(appointment_booked=True)),
        transfers=Count("id", filter=Q(human_transferred=True)),
        after_hours_calls=Count("id", filter=Q(after_hours=True)),
        cost=Sum("cost_usd"),
        rev=Sum("attributed_revenue_usd"),
    )
    total_calls = call_agg["total_calls"] or 0
    booked_calls = call_agg["booked_calls"] or 0
    booking_rate = round(booked_calls / total_calls, 4) if total_calls else 0.0

    metrics = {
        "total_calls": total_calls,
        "booked_calls": booked_calls,
        "booking_rate": booking_rate,
        "transfers": call_agg["transfers"] or 0,
        "after_hours_calls": call_agg["after_hours_calls"] or 0,
        "estimated_voice_cost_usd": round(call_agg["cost"] or 0.0, 2),
        "attributed_revenue_usd": round(call_agg["rev"] or 0.0, 2),
    }

    calls = [
        {
            "call_id": c.call_id,
            "duration_seconds": c.duration_seconds,
            "appointment_booked": c.appointment_booked,
            "human_transferred": c.human_transferred,
            "after_hours": c.after_hours,
            "attributed_revenue_usd": c.attributed_revenue_usd,
            "summary": c.summary,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for c in CallTelemetryLog.objects.filter(tenant=tenant).order_by("-created_at")[:25]
    ]

    bookings = [
        {
            "id": b.id,
            "resource_id": b.resource_id,
            "slot_iso": b.slot_iso,
            "caller_name": b.caller_name,
            "service_type": b.service_type,
            "duration_minutes": b.duration_minutes,
            "status": b.status,
        }
        for b in AppointmentSlotLock.objects.filter(tenant=tenant).order_by("-created_at")[:25]
    ]

    return JsonResponse({
        "tenant": {
            "tenant_id": tenant.tenant_id,
            "business_name": tenant.business_name,
            "vertical": tenant.vertical,
        },
        "metrics": metrics,
        "calls": calls,
        "bookings": bookings,
    })

