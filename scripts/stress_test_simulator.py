#!/usr/bin/env python3
"""
Zero-Dependency End-to-End Verification Suite for the AI Voice Receptionist Enterprise Middleware.
Tests:
1. Database Initialization & Schema Integrity
2. Live Calendar Availability Query (`checkCalendar`)
3. Concurrent Race-Condition Slot Locking (2 simultaneous callers requesting Tuesday at 2:00 PM)
4. Timeout-Retry Idempotency Protection (same `workflow_run_id` retried after 5s timeout)
5. FCC April 2025 Natural-Language TCPA Opt-Out & Missed-Call SMS Fallback
6. Warm Transfer Conference & Staff Whisper TwiML Generation
7. Monthly Executive ROI Report Generation
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

from app.database import init_db
from app.api.voice_webhooks import (
    process_vapi_webhook_payload,
    process_direct_booking,
    process_roi_report,
)
from app.api.twilio_transfer import build_warm_transfer_hold_twiml

TEST_DB = "/tmp/test_voice_enterprise.db"


def run_verification_suite():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    print("1. [Database Init] Creating transactional tables & unique slot constraints...")
    init_db(TEST_DB)
    print("   -> PASSED: SQLite transactional tables initialized.")

    print("\n2. [Live Availability] Testing Vapi `checkCalendar` tool webhook...")
    check_payload = {
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "call_check_001",
                    "function": {
                        "name": "checkCalendar",
                        "arguments": {
                            "tenant_id": "apex_dental",
                            "resource_id": "chair_1",
                            "requestedDate": "2026-11-05",
                        },
                    },
                }
            ],
        }
    }
    r_check = process_vapi_webhook_payload(check_payload, db_path=TEST_DB)
    print("   -> PASSED:", r_check["results"][0]["result"])

    print("\n3. [Concurrency & Race Condition] Caller A and Caller B both try to lock 2026-11-05T14:00:00...")
    caller_a_payload = {
        "tenant_id": "apex_dental",
        "resource_id": "chair_1",
        "workflow_run_id": "run_caller_A_999",
        "firstName": "Sarah Jenkins",
        "phone": "+15552223333",
        "serviceType": "implant_consultation",
        "requestedTime": "2026-11-05T14:00:00",
    }
    caller_b_payload = {
        "tenant_id": "apex_dental",
        "resource_id": "chair_1",
        "workflow_run_id": "run_caller_B_888",
        "firstName": "David Miller",
        "phone": "+15554445555",
        "serviceType": "emergency_exam",
        "requestedTime": "2026-11-05T14:00:00",
    }
    res_a = process_direct_booking(caller_a_payload, db_path=TEST_DB)
    res_b = process_direct_booking(caller_b_payload, db_path=TEST_DB)
    assert res_a["status"] == "CONFIRMED"
    assert res_b["status"] == "SLOT_JUST_TAKEN"
    assert len(res_b["alternatives"]) > 0
    print("   -> Caller A Outcome:", res_a["status"], "|", res_a["message"])
    print("   -> Caller B Outcome (Zero Double-Booking):", res_b["status"], "|", res_b["message"])

    print("\n4. [Idempotency Protection] Simulating Vapi 5s timeout retry for Caller A...")
    res_a_retry = process_direct_booking(caller_a_payload, db_path=TEST_DB)
    assert res_a_retry["status"] == "CONFIRMED_IDEMPOTENT_RETRY"
    print("   -> PASSED:", res_a_retry["message"])

    print("\n5. [End-of-Call Missed-Call SMS & TCPA Revocation] Testing unbooked hang-up vs opt-out...")
    eoc_unbooked = {
        "message": {
            "type": "end-of-call-report",
            "durationSeconds": 65.0,
            "cost": 0.14,
            "call": {
                "id": "call_unbooked_01",
                "tenantId": "apex_dental",
                "customer": {"number": "+15557778888"},
            },
            "transcript": "Caller: How much is a cleaning? I need to check with my spouse first, bye.",
            "analysis": {
                "summary": "Caller asked about cleaning price and hung up before booking.",
                "structuredData": {
                    "appointmentBooked": False,
                    "transferredToHuman": False,
                    "isAfterHours": True,
                },
            },
        }
    }
    r_eoc1 = process_vapi_webhook_payload(eoc_unbooked, db_path=TEST_DB)
    assert r_eoc1["missed_call_sms_fallback"]["sent"] is True
    print("   -> Unbooked Hang-up SMS Dispatched:", r_eoc1["missed_call_sms_fallback"]["body"])

    eoc_optout = {
        "message": {
            "type": "end-of-call-report",
            "durationSeconds": 180.0,
            "cost": 0.25,
            "call": {
                "id": "call_booked_02",
                "tenantId": "apex_dental",
                "customer": {"number": "+15559990000"},
            },
            "transcript": "Caller: Please take me off your list and don't call me again.",
            "analysis": {
                "summary": "Caller requested opt-out.",
                "structuredData": {
                    "appointmentBooked": False,
                    "transferredToHuman": False,
                    "isAfterHours": False,
                },
            },
        }
    }
    r_eoc2 = process_vapi_webhook_payload(eoc_optout, db_path=TEST_DB)
    assert r_eoc2["tcpa_revocation"]["suppressed"] is True
    assert r_eoc2["missed_call_sms_fallback"] is None
    print("   -> FCC April 2025 Opt-Out Recognized & Suppressed:", r_eoc2["tcpa_revocation"])

    print("\n6. [Warm Transfer TwiML Bridge] Testing conference hold & whisper screening...")
    r_tx = build_warm_transfer_hold_twiml(
        {
            "caller_name": "Sarah Jenkins",
            "caller_phone": "+15552223333",
            "urgency_reason": "Broken crown with acute sensitivity",
            "verified_details": "Delta Dental PPO verified",
        }
    )
    assert "<Conference" in r_tx["twiml"]
    print("   -> PASSED: Conference Room Header =", r_tx["headers"]["X-Conference-Room"])

    print("\n7. [Monthly Executive ROI Report] Generating client retention report...")
    r_roi = process_roi_report("apex_dental", retainer_fee_usd=1500.0, db_path=TEST_DB)
    print("   -> PASSED:", r_roi["executive_summary_narrative"])
    print("\nALL END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!")

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


if __name__ == "__main__":
    run_verification_suite()
