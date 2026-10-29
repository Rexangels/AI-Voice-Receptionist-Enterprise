import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

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
    conn: sqlite3.Connection,
    tenant_id: str,
    resource_id: str,
    target_date_str: str,
    max_options: int = 3,
) -> List[str]:
    """
    Returns up to `max_options` available ISO slots on `target_date_str` (YYYY-MM-DD)
    so the voice agent only reads 2-3 clear options aloud to the caller.
    """
    try:
        base_date = datetime.strptime(target_date_str[:10], "%Y-%m-%d")
    except ValueError:
        return []

    cur = conn.execute(
        """
        SELECT slot_iso, duration_minutes FROM appointment_slot_locks
        WHERE tenant_id = ? AND resource_id = ? AND status = 'CONFIRMED'
        """,
        (tenant_id, resource_id),
    )
    busy = []
    for row in cur.fetchall():
        try:
            start = datetime.fromisoformat(row["slot_iso"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            else:
                start = start.astimezone(timezone.utc)
            busy.append((start, start + timedelta(minutes=int(row["duration_minutes"] or 60))))
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
    conn: sqlite3.Connection,
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
    Implements the Read-Offer-Lock-Write-ReadBack transactional pattern:
    1. Enforces the Verbal Confirmation Gate (`verbal_confirmed`).
    2. Checks `idempotency_key` first: if the voice platform timed out at 5s and retried,
       returns the already-committed booking without throwing an error or duplicating.
    3. Attempts an atomic INSERT protected by `UNIQUE(tenant_id, resource_id, slot_iso)`.
    4. If another concurrent caller locked the exact same resource+timestamp milliseconds
       earlier, catches sqlite3.IntegrityError, rolls back, and returns `SLOT_JUST_TAKEN`
       with the next 2 open alternative slots so the agent resolves it in the same turn.
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

    # Step 1: Idempotency check (handles timeout retries seamlessly)
    cur = conn.execute(
        "SELECT * FROM appointment_slot_locks WHERE idempotency_key = ?",
        (idempotency_key,),
    )
    existing = cur.fetchone()
    if existing:
        return {
            "status": "CONFIRMED_IDEMPOTENT_RETRY",
            "booking_id": existing["id"],
            "slot_iso": existing["slot_iso"],
            "resource_id": existing["resource_id"],
            "message": (
                f"Slot confirmed for {existing['caller_name']} at {existing['slot_iso']}. "
                f"(Idempotent retry recognized; no duplicate created.)"
            ),
        }

    duration_minutes = SERVICE_DURATION_MAP.get(service_type, 60)

    try:
        requested_start = datetime.fromisoformat(slot_iso)
    except (TypeError, ValueError):
        return {"status": "INVALID_SLOT", "message": "Please request a valid ISO date and time."}
    if requested_start.tzinfo is None:
        requested_start = requested_start.replace(tzinfo=timezone.utc)
    else:
        requested_start = requested_start.astimezone(timezone.utc)
    requested_end = requested_start + timedelta(minutes=duration_minutes)
    existing_slots = conn.execute(
        "SELECT slot_iso, duration_minutes FROM appointment_slot_locks WHERE tenant_id = ? AND resource_id = ? AND status = 'CONFIRMED'",
        (tenant_id, resource_id),
    ).fetchall()
    for row in existing_slots:
        try:
            busy_start = datetime.fromisoformat(row["slot_iso"])
            busy_start = busy_start.replace(tzinfo=timezone.utc) if busy_start.tzinfo is None else busy_start.astimezone(timezone.utc)
            busy_end = busy_start + timedelta(minutes=int(row["duration_minutes"] or 60))
            if requested_start < busy_end and requested_end > busy_start:
                return {
                    "status": "SLOT_JUST_TAKEN",
                    "slot_iso": slot_iso,
                    "alternatives": get_open_slots(conn, tenant_id, resource_id, slot_iso[:10], max_options=2),
                    "message": f"SLOT_JUST_TAKEN: {slot_iso} overlaps an existing appointment. Offer another available time.",
                }
        except (TypeError, ValueError):
            continue

    # Step 2: Atomic insertion with unique constraint lock
    try:
        cur = conn.execute(
            """
            INSERT INTO appointment_slot_locks
            (tenant_id, resource_id, slot_iso, idempotency_key, caller_name, caller_phone, service_type, duration_minutes, verbal_confirmed, skill_verified, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 'CONFIRMED')
            """,
            (
                tenant_id,
                resource_id,
                slot_iso,
                idempotency_key,
                caller_name,
                caller_phone,
                service_type,
                duration_minutes,
            ),
        )
        conn.commit()
        return {
            "status": "CONFIRMED",
            "booking_id": cur.lastrowid,
            "slot_iso": slot_iso,
            "resource_id": resource_id,
            "duration_minutes": duration_minutes,
            "message": (
                f"Slot confirmed for {caller_name} on {slot_iso} ({service_type}, {duration_minutes} mins). "
                f"Booking created for {caller_phone}; send a confirmation through a configured messaging provider if available."
            ),
        }
    except sqlite3.IntegrityError:
        conn.rollback()
        alternatives = get_open_slots(
            conn=conn,
            tenant_id=tenant_id,
            resource_id=resource_id,
            target_date_str=slot_iso[:10],
            max_options=2,
        )
        alt_text = ", ".join(alternatives) if alternatives else "tomorrow morning at 9:00 AM"
        return {
            "status": "SLOT_JUST_TAKEN",
            "slot_iso": slot_iso,
            "alternatives": alternatives,
            "message": (
                f"SLOT_JUST_TAKEN: That exact time ({slot_iso}) was just reserved moments ago. "
                f"Please offer the caller these open times instead: {alt_text}."
            ),
        }


def update_booking_status(
    conn: sqlite3.Connection, booking_id: int, tenant_id: str, new_status: str
) -> Dict[str, Any]:
    normalized = (new_status or "").strip().upper().replace("-", "_").replace(" ", "_")
    if normalized not in VALID_BOOKING_STATUSES:
        return {
            "updated": False,
            "reason": f"Invalid status '{new_status}'. Allowed: {sorted(VALID_BOOKING_STATUSES)}",
        }

    cur = conn.execute(
        "SELECT * FROM appointment_slot_locks WHERE id = ? AND tenant_id = ?",
        (booking_id, tenant_id),
    )
    row = cur.fetchone()
    if not row:
        return {"updated": False, "reason": "booking_not_found"}

    conn.execute(
        "UPDATE appointment_slot_locks SET status = ? WHERE id = ? AND tenant_id = ?",
        (normalized, booking_id, tenant_id),
    )
    conn.commit()
    return {
        "updated": True,
        "booking_id": booking_id,
        "caller_name": row["caller_name"],
        "slot_iso": row["slot_iso"],
        "previous_status": row["status"],
        "status": normalized,
    }


def release_booked_slot(conn: sqlite3.Connection, booking_id: int, tenant_id: str) -> Dict[str, Any]:
    cur = conn.execute(
        "SELECT * FROM appointment_slot_locks WHERE id = ? AND tenant_id = ?",
        (booking_id, tenant_id),
    )
    row = cur.fetchone()
    if not row:
        return {"released": False, "reason": "booking_not_found"}

    conn.execute(
        "DELETE FROM appointment_slot_locks WHERE id = ? AND tenant_id = ?",
        (booking_id, tenant_id),
    )
    conn.commit()
    return {
        "released": True,
        "booking_id": booking_id,
        "slot_iso": row["slot_iso"],
        "caller_name": row["caller_name"],
    }
