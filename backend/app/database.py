import sqlite3
from contextlib import contextmanager
from app.config import settings


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    target = db_path or settings.SQLITE_DB_PATH
    conn = sqlite3.connect(target, timeout=10.0, isolation_level="IMMEDIATE")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transactional_db(db_path: str | None = None):
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    """
    Initializes the transactional tables with strict UNIQUE constraints:
    - `appointment_slot_locks`: Enforces `UNIQUE(tenant_id, resource_id, slot_iso)` to prevent
      concurrent call race conditions, and `UNIQUE(idempotency_key)` to prevent duplicate commits
      from 5-second voice tool timeouts.
    - `call_telemetry_logs`: Tracks call durations, costs, after-hours capture, and pipeline ROI.
    - `suppression_registry`: Tracks FCC April 2025 Enhanced TCPA Revocation opt-outs.
    """
    with transactional_db(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS appointment_slot_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL DEFAULT 'default_clinic',
                resource_id TEXT NOT NULL DEFAULT 'chair_1',
                slot_iso TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                caller_name TEXT NOT NULL,
                caller_phone TEXT NOT NULL,
                service_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'CONFIRMED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, resource_id, slot_iso)
            );

            CREATE TABLE IF NOT EXISTS call_telemetry_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL DEFAULT 'default_clinic',
                caller_phone TEXT,
                duration_seconds REAL DEFAULT 0.0,
                cost_usd REAL DEFAULT 0.0,
                appointment_booked INTEGER DEFAULT 0,
                human_transferred INTEGER DEFAULT 0,
                after_hours INTEGER DEFAULT 0,
                attributed_revenue_usd REAL DEFAULT 0.0,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS suppression_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL DEFAULT 'default_clinic',
                phone_number TEXT NOT NULL,
                revocation_phrase TEXT,
                channel TEXT DEFAULT 'voice',
                revoked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, phone_number)
            );
            """
        )
        conn.commit()
