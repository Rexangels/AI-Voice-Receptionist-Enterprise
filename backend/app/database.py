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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_def: str) -> None:
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cur.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")


def init_db(db_path: str | None = None) -> None:
    """
    Initializes the transactional tables with strict UNIQUE constraints:
    - `tenants`: Multi-tenant commercial settings, minute allowances, overage rates, and telecom trust posture.
    - `appointment_slot_locks`: Enforces `UNIQUE(tenant_id, resource_id, slot_iso)` to prevent
      concurrent call race conditions, and `UNIQUE(idempotency_key)` to prevent duplicate commits
      from 5-second voice tool timeouts.
    - `call_telemetry_logs`: Tracks call durations, costs, acoustic P50/P95/TTFA latency, after-hours capture, and pipeline ROI.
    - `suppression_registry`: Tracks FCC April 2025 Enhanced TCPA Revocation opt-outs.
    - `onboarding_runs`: Tracks 5-stage autonomous client onboarding runs and generated Kickoff Briefs.
    """
    with transactional_db(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                business_name TEXT NOT NULL,
                vertical TEXT NOT NULL DEFAULT 'dental',
                tier_name TEXT NOT NULL DEFAULT 'Custom Built & Operated ($1M-$20M)',
                retainer_fee_usd REAL NOT NULL DEFAULT 1500.0,
                setup_fee_usd REAL NOT NULL DEFAULT 4500.0,
                included_minutes INTEGER NOT NULL DEFAULT 1500,
                overage_rate_per_min_usd REAL NOT NULL DEFAULT 0.20,
                avg_ticket_usd REAL NOT NULL DEFAULT 450.0,
                close_rate REAL NOT NULL DEFAULT 0.35,
                escalation_phone TEXT NOT NULL DEFAULT '+15550123456',
                orchestrator TEXT NOT NULL DEFAULT 'Retell AI + Telnyx SIP',
                hipaa_baa_status TEXT NOT NULL DEFAULT 'Active (Self-Serve BAA)',
                shaken_stir_status TEXT NOT NULL DEFAULT 'Level A Attested',
                a2p_10dlc_status TEXT NOT NULL DEFAULT 'TCR Approved',
                supported_skills TEXT NOT NULL DEFAULT 'implant_consultation,emergency_exam,emergency_crown_repair,routine_cleaning,dental_consultation,general_inquiry',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS appointment_slot_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL DEFAULT 'default_clinic',
                resource_id TEXT NOT NULL DEFAULT 'chair_1',
                slot_iso TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                caller_name TEXT NOT NULL,
                caller_phone TEXT NOT NULL,
                service_type TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL DEFAULT 60,
                verbal_confirmed INTEGER NOT NULL DEFAULT 1,
                skill_verified INTEGER NOT NULL DEFAULT 1,
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
                turn_latency_p50_ms INTEGER DEFAULT 540,
                turn_latency_p95_ms INTEGER DEFAULT 720,
                ttfa_ms INTEGER DEFAULT 125,
                appointment_booked INTEGER DEFAULT 0,
                human_transferred INTEGER DEFAULT 0,
                after_hours INTEGER DEFAULT 0,
                race_conflict_prevented INTEGER DEFAULT 0,
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

            CREATE TABLE IF NOT EXISTS onboarding_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                business_name TEXT NOT NULL,
                vertical TEXT NOT NULL,
                annual_revenue_band TEXT NOT NULL,
                setup_fee_usd REAL NOT NULL,
                retainer_fee_usd REAL NOT NULL,
                stripe_ach_fee_usd REAL NOT NULL,
                card_fee_saved_usd REAL NOT NULL,
                kickoff_brief TEXT NOT NULL,
                flagged_risks TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Ensure backward-compatible schema migrations if DB file already existed
        _ensure_column(conn, "appointment_slot_locks", "duration_minutes", "INTEGER NOT NULL DEFAULT 60")
        _ensure_column(conn, "appointment_slot_locks", "verbal_confirmed", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "appointment_slot_locks", "skill_verified", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "call_telemetry_logs", "turn_latency_p50_ms", "INTEGER DEFAULT 540")
        _ensure_column(conn, "call_telemetry_logs", "turn_latency_p95_ms", "INTEGER DEFAULT 720")
        _ensure_column(conn, "call_telemetry_logs", "ttfa_ms", "INTEGER DEFAULT 125")
        _ensure_column(conn, "call_telemetry_logs", "race_conflict_prevented", "INTEGER DEFAULT 0")
        conn.commit()
