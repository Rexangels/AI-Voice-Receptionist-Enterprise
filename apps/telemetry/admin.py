from django.contrib import admin
from apps.telemetry.models import CallTelemetryLog, OnboardingRun


@admin.register(CallTelemetryLog)
class CallTelemetryLogAdmin(admin.ModelAdmin):
    list_display = (
        "call_id",
        "tenant",
        "caller_phone",
        "duration_seconds",
        "cost_usd",
        "appointment_booked",
        "human_transferred",
        "after_hours",
        "attributed_revenue_usd",
        "turn_latency_p50_ms",
        "created_at",
    )
    list_filter = ("appointment_booked", "human_transferred", "after_hours", "tenant")
    search_fields = ("call_id", "caller_phone", "summary")
    readonly_fields = ("created_at",)


@admin.register(OnboardingRun)
class OnboardingRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "business_name",
        "vertical",
        "annual_revenue_band",
        "setup_fee_usd",
        "retainer_fee_usd",
        "stripe_ach_fee_usd",
        "created_at",
    )
    list_filter = ("vertical", "annual_revenue_band")
    search_fields = ("business_name", "kickoff_brief")
    readonly_fields = ("created_at",)

