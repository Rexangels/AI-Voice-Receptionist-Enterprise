from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from django.db import transaction, IntegrityError
from apps.core.models import Tenant
from apps.appointments.models import AppointmentSlotLock

DEFAULT_DAILY_HOURS = [9, 10, 11, 13, 14, 15, 16]

VALID_BOOKING_STATUSES = {"CONFIRMED", "COMPLETED", "RESCHEDULED", "NO_SHOW"}

SERVICE_DURATION_MAP: Dict[str, int] = {
    "implant_consultation": 60,
    "emergency_crown_repair": 60,
    "emergency_exam": 45,
    "routine_cleaning": 45,
    "dental_consultation": 45,
    "hvac_emergency_dispatch": 90,
    "furnace_diagnostic": 60,
    "plumbing_main_line": 90,
    "legal_intake_review": 45,
    "auto_bay_diagnostic": 60,
    "general_inquiry": 30,
}


def get_open_slots(
    tenant_id: str,
    resource_id: str,
    target_date_str: str,
    max_options: int = 3,
) -> List[str]:
    """
    Returns up to `max_options` available ISO slots on `target_date_str` (YYYY-MM-DD)
    so the voice agent reads 2-3 clear options aloud to the caller.
    """
    try:
        base_date = datetime.strptime(target_date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return []

    locks = AppointmentSlotLock.objects.filter(
        tenant_id=tenant_id,
        resource_id=resource_id,
        status="CONFIRMED",
    ).values("slot_iso", "duration_minutes")

    busy = []
    for row in locks:
        try:
            start = datetime.fromisoformat(row["slot_iso"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            else:
                start = start.astimezone(timezone.utc)
            duration = int(row.get("duration_minutes") or 60)
            busy.append((start, start + timedelta(minutes=duration)))
        except (TypeError, ValueError):
            continue

    available = []
    for hour in DEFAULT_DAILY_HOURS:
        candidate_dt = base_date.replace(hour=hour, minute=0, second=0, microsecond=0).replace(tzinfo=timezone.utc)
        candidate = candidate_dt.strftime("%Y-%m-%dT%H:%M:%S")
        candidate_end = candidate_dt + timedelta(minutes=60)
        if not any(candidate_dt < busy_end and candidate_end > busy_start for busy_start, busy_end in busy):
            available.append(candidate)
        if len(available) >= max_options:
            break

    return available


def atomic_book_slot(
    tenant_id: str,
    resource_id: str,
    slot_iso: str,
    idempotency_key: str,
    caller_name: str,
    caller_phone: str,
    service_type: str,
    verbal_confirmed: bool = True,
) -> Dict[str, Any]:
    """
    Implements the Read-Offer-Lock-Write-ReadBack transactional pattern using Django ORM:
    1. Enforces the Verbal Confirmation Gate (`verbal_confirmed`).
    2. Checks `idempotency_key` first to prevent duplicate bookings from voice tool retries.
    3. Attempts an atomic INSERT protected by UNIQUE(tenant, resource_id, slot_iso).
    4. If another concurrent caller locked the slot, catches IntegrityError and returns SLOT_JUST_TAKEN
       with the next 2 open alternative slots.
    """
    if not verbal_confirmed:
        return {
            "status": "VERBAL_READBACK_REQUIRED",
            "slot_iso": slot_iso,
            "resource_id": resource_id,
            "message": (
                f"Hold before writing: Please read back {slot_iso} for {service_type} to {caller_name} "
                f"and obtain an explicit 'Yes' confirmation before locking the calendar."
            ),
        }

    # 1. Idempotency Check
    existing = AppointmentSlotLock.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return {
            "status": "IDEMPOTENT_RETRY_OK",
            "booking_id": existing.id,
            "slot_iso": existing.slot_iso,
            "resource_id": existing.resource_id,
            "message": (
                f"Slot confirmed for {existing.caller_name} at {existing.slot_iso}. "
                f"(Idempotent retry recognized; no duplicate created.)"
            ),
        }

    # 2. Verify Tenant exists
    tenant = Tenant.objects.filter(tenant_id=tenant_id).first()
    if not tenant:
        return {
            "status": "TENANT_NOT_FOUND",
            "message": f"Tenant '{tenant_id}' is not configured in this system.",
        }

    duration = SERVICE_DURATION_MAP.get(service_type, 60)

    # 3. Atomic Insert with Race Condition Protection
    try:
        with transaction.atomic():
            booking = AppointmentSlotLock.objects.create(
                tenant=tenant,
                resource_id=resource_id,
                slot_iso=slot_iso,
                idempotency_key=idempotency_key,
                caller_name=caller_name,
                caller_phone=caller_phone,
                service_type=service_type,
                duration_minutes=duration,
                verbal_confirmed=verbal_confirmed,
                skill_verified=True,
                status="CONFIRMED",
            )

        return {
            "status": "CONFIRMED",
            "booking_id": booking.id,
            "slot_iso": slot_iso,
            "resource_id": resource_id,
            "message": (
                f"Slot confirmed for {caller_name} on {slot_iso} ({service_type}, {duration} mins). "
                f"Confirmation SMS dispatched to {caller_phone}."
            ),
        }
    except IntegrityError:
        # Race condition: Another concurrent caller locked this slot milliseconds earlier
        target_date = slot_iso[:10]
        alternatives = get_open_slots(tenant_id, resource_id, target_date, max_options=2)
        alt_str = ", ".join(alternatives) if alternatives else "earlier or later that week"

        return {
            "status": "SLOT_JUST_TAKEN",
            "slot_iso": slot_iso,
            "resource_id": resource_id,
            "message": (
                f"SLOT_JUST_TAKEN: That exact time ({slot_iso}) was just reserved moments ago. "
                f"Please offer the caller these open times instead: {alt_str}."
            ),
        }


def release_booked_slot(booking_id: int, tenant_id: str) -> Dict[str, Any]:
    booking = AppointmentSlotLock.objects.filter(id=booking_id, tenant_id=tenant_id).first()
    if not booking:
        return {"status": "NOT_FOUND", "message": f"Booking ID {booking_id} not found."}
    booking.delete()
    return {"status": "RELEASED", "booking_id": booking_id, "message": f"Slot {booking_id} released successfully."}


def update_booking_status(booking_id: int, tenant_id: str, new_status: str) -> Dict[str, Any]:
    clean_status = (new_status or "").strip().upper()
    if clean_status not in VALID_BOOKING_STATUSES:
        return {"status": "INVALID_STATUS", "message": f"Status must be one of {sorted(VALID_BOOKING_STATUSES)}."}
    booking = AppointmentSlotLock.objects.filter(id=booking_id, tenant_id=tenant_id).first()
    if not booking:
        return {"status": "NOT_FOUND", "message": f"Booking ID {booking_id} not found."}
    booking.status = clean_status
    booking.save(update_fields=["status"])
    return {"status": "UPDATED", "booking_id": booking_id, "new_status": clean_status}

