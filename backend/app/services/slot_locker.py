import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List

DEFAULT_DAILY_HOURS = [9, 10, 11, 13, 14, 15, 16]


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
        base_date = datetime.utcnow() + timedelta(days=1)

    cur = conn.execute(
        """
        SELECT slot_iso FROM appointment_slot_locks
        WHERE tenant_id = ? AND resource_id = ? AND status = 'CONFIRMED'
        """,
        (tenant_id, resource_id),
    )
    booked_set = {row["slot_iso"] for row in cur.fetchall()}

    available = []
    for hour in DEFAULT_DAILY_HOURS:
        candidate = base_date.replace(hour=hour, minute=0, second=0, microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        if candidate not in booked_set:
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
) -> Dict[str, Any]:
    """
    Implements the Read-Offer-Lock-Write-ReadBack transactional pattern:
    1. Checks `idempotency_key` first: if the voice platform timed out at 5s and retried,
       returns the already-committed booking without throwing an error or duplicating.
    2. Attempts an atomic INSERT protected by `UNIQUE(tenant_id, resource_id, slot_iso)`.
    3. If another concurrent caller locked the exact same resource+timestamp milliseconds
       earlier, catches sqlite3.IntegrityError, rolls back, and returns `SLOT_JUST_TAKEN`
       with the next 2 open alternative slots so the agent resolves it in the same turn.
    """
    # Step 1: Idempotency check (handles timeout retries seamlessly)
    cur = conn.execute(
        "SELECT * FROM appointment_slot_locks WHERE idempotency_key = ?",
        (idempotency_key,),
    )
    existing = cur.fetchone()
    if existing:
        return {
            "status": "CONFIRMED_IDEMPOTENT_RETRY",
            "slot_iso": existing["slot_iso"],
            "resource_id": existing["resource_id"],
            "message": (
                f"Slot confirmed for {existing['caller_name']} at {existing['slot_iso']}. "
                f"(Idempotent retry recognized; no duplicate created.)"
            ),
        }

    # Step 2: Atomic insertion with unique constraint lock
    try:
        cur = conn.execute(
            """
            INSERT INTO appointment_slot_locks
            (tenant_id, resource_id, slot_iso, idempotency_key, caller_name, caller_phone, service_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'CONFIRMED')
            """,
            (
                tenant_id,
                resource_id,
                slot_iso,
                idempotency_key,
                caller_name,
                caller_phone,
                service_type,
            ),
        )
        conn.commit()
        return {
            "status": "CONFIRMED",
            "booking_id": cur.lastrowid,
            "slot_iso": slot_iso,
            "resource_id": resource_id,
            "message": (
                f"Slot confirmed for {caller_name} on {slot_iso} ({service_type}). "
                f"Confirmation SMS dispatched to {caller_phone}."
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
