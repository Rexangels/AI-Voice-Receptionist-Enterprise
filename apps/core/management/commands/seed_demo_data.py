from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.models import Tenant, User
from apps.appointments.models import AppointmentSlotLock
from apps.telemetry.models import CallTelemetryLog


class Command(BaseCommand):
    help = "Seeds initial demo tenants, appointments, calls, and bootstraps the admin user if configured."

    def handle(self, *args, **options):
        # 1. Bootstrap Admin/Owner
        email = settings.BOOTSTRAP_ADMIN_EMAIL
        password = settings.BOOTSTRAP_ADMIN_PASSWORD
        if email and password and len(password) >= 12:
            owner, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": "Agency Owner",
                    "role": "owner",
                    "status": "ACTIVE",
                    "business_name": "Agency",
                    "vertical": "agency",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            owner.set_password(password)
            owner.is_staff = True
            owner.is_superuser = True
            owner.role = "owner"
            owner.status = "ACTIVE"
            owner.save()
            self.stdout.write(self.style.SUCCESS(f"Bootstrapped owner account for {email}."))

        # 2. Check if Tenants exist
        if Tenant.objects.count() > 0:
            self.stdout.write("Tenants already exist. Skipping demo data seeding.")
            return

        self.stdout.write("Seeding demo tenants and calls...")

        apex = Tenant.objects.create(
            tenant_id="default_clinic",
            business_name="Apex Dental & Implant Studio",
            vertical="dental",
            tier_name="Custom Built & Operated ($1M–$20M)",
            retainer_fee_usd=1500.0,
            setup_fee_usd=4500.0,
            included_minutes=1500,
            overage_rate_per_min_usd=0.20,
            avg_ticket_usd=450.0,
            close_rate=0.35,
            escalation_phone="+15550123456",
            orchestrator="Retell AI + Telnyx SIP",
            hipaa_baa_status="Active (Self-Serve BAA $0/mo)",
            shaken_stir_status="Level A Attested",
            a2p_10dlc_status="TCR Approved",
        )

        primeflow = Tenant.objects.create(
            tenant_id="primeflow_hvac",
            business_name="PrimeFlow Heating, Cooling & Plumbing",
            vertical="hvac_plumbing",
            tier_name="Custom Built & Operated ($1M–$20M)",
            retainer_fee_usd=2000.0,
            setup_fee_usd=6000.0,
            included_minutes=2000,
            overage_rate_per_min_usd=0.20,
            avg_ticket_usd=850.0,
            close_rate=0.30,
            escalation_phone="+15550198877",
            orchestrator="Vapi + Telnyx SIP + Cartesia Sonic",
            hipaa_baa_status="Standard Commercial",
            shaken_stir_status="Level A Attested",
            a2p_10dlc_status="TCR Approved",
        )

        Tenant.objects.create(
            tenant_id="metro_legal",
            business_name="Metro Personal Injury & Intake Law",
            vertical="legal",
            tier_name="Full AI Operations Stack ($5M–$20M+)",
            retainer_fee_usd=3500.0,
            setup_fee_usd=9000.0,
            included_minutes=3000,
            overage_rate_per_min_usd=0.22,
            avg_ticket_usd=2400.0,
            close_rate=0.25,
            escalation_phone="+15550144411",
            orchestrator="Retell AI + Twilio Elastic SIP",
            hipaa_baa_status="SOC 2 Type II + Zero Data Retention",
            shaken_stir_status="Level A Attested",
            a2p_10dlc_status="TCR Approved",
        )

        # Seed Bookings
        AppointmentSlotLock.objects.create(
            tenant=apex,
            resource_id="chair_1",
            slot_iso="2026-11-05T09:00:00",
            idempotency_key="default_clinic:seed_run_001:2026-11-05T09:00:00",
            caller_name="Sarah Jenkins",
            caller_phone="+15552223333",
            service_type="implant_consultation",
            duration_minutes=60,
            status="CONFIRMED",
        )
        AppointmentSlotLock.objects.create(
            tenant=apex,
            resource_id="chair_1",
            slot_iso="2026-11-05T10:00:00",
            idempotency_key="default_clinic:seed_run_002:2026-11-05T10:00:00",
            caller_name="Marcus Vance",
            caller_phone="+15553334444",
            service_type="emergency_crown_repair",
            duration_minutes=60,
            status="CONFIRMED",
        )
        AppointmentSlotLock.objects.create(
            tenant=apex,
            resource_id="chair_2",
            slot_iso="2026-11-05T13:00:00",
            idempotency_key="default_clinic:seed_run_003:2026-11-05T13:00:00",
            caller_name="Dr. Aris Thorne",
            caller_phone="+15554445555",
            service_type="routine_cleaning",
            duration_minutes=45,
            status="CONFIRMED",
        )
        AppointmentSlotLock.objects.create(
            tenant=primeflow,
            resource_id="truck_bay_1",
            slot_iso="2026-11-05T09:00:00",
            idempotency_key="primeflow_hvac:seed_hvac_001:2026-11-05T09:00:00",
            caller_name="Robert Chen",
            caller_phone="+15559012345",
            service_type="hvac_emergency_dispatch",
            duration_minutes=90,
            status="CONFIRMED",
        )

        # Seed Call Telemetry
        CallTelemetryLog.objects.create(
            call_id="call_seed_101",
            tenant=apex,
            caller_phone="+15552223333",
            duration_seconds=118.0,
            cost_usd=0.16,
            appointment_booked=True,
            human_transferred=False,
            after_hours=True,
            turn_latency_p50_ms=520,
            turn_latency_p95_ms=690,
            ttfa_ms=115,
            attributed_revenue_usd=450.0,
            summary="Booked implant consultation for Sarah Jenkins (Chair 1).",
        )
        CallTelemetryLog.objects.create(
            call_id="call_seed_102",
            tenant=apex,
            caller_phone="+15553334444",
            duration_seconds=94.0,
            cost_usd=0.13,
            appointment_booked=True,
            human_transferred=False,
            after_hours=False,
            turn_latency_p50_ms=540,
            turn_latency_p95_ms=710,
            ttfa_ms=122,
            attributed_revenue_usd=450.0,
            summary="Booked emergency crown repair for Marcus Vance.",
        )
        CallTelemetryLog.objects.create(
            call_id="call_seed_201",
            tenant=primeflow,
            caller_phone="+15559012345",
            duration_seconds=130.0,
            cost_usd=0.17,
            appointment_booked=True,
            human_transferred=False,
            after_hours=True,
            turn_latency_p50_ms=495,
            turn_latency_p95_ms=660,
            ttfa_ms=108,
            attributed_revenue_usd=850.0,
            summary="After-hours emergency furnace dispatch locked for Robert Chen.",
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded initial demo tenants, bookings, and calls."))

