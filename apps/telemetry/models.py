from django.db import models
from apps.core.models import Tenant


class CallTelemetryLog(models.Model):
    call_id = models.CharField(max_length=128, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="call_logs")
    caller_phone = models.CharField(max_length=32, blank=True, null=True)
    duration_seconds = models.FloatField(default=0.0)
    cost_usd = models.FloatField(default=0.0)
    turn_latency_p50_ms = models.IntegerField(default=540)
    turn_latency_p95_ms = models.IntegerField(default=720)
    ttfa_ms = models.IntegerField(default=125)
    appointment_booked = models.BooleanField(default=False)
    human_transferred = models.BooleanField(default=False)
    after_hours = models.BooleanField(default=False)
    race_conflict_prevented = models.BooleanField(default=False)
    attributed_revenue_usd = models.FloatField(default=0.0)
    summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "call_telemetry_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Call {self.call_id} | {self.tenant_id} ({'Booked' if self.appointment_booked else 'Unbooked'})"


class OnboardingRun(models.Model):
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL, related_name="onboarding_runs")
    business_name = models.CharField(max_length=255)
    vertical = models.CharField(max_length=64)
    annual_revenue_band = models.CharField(max_length=64)
    setup_fee_usd = models.FloatField(default=4500.0)
    retainer_fee_usd = models.FloatField(default=1500.0)
    stripe_ach_fee_usd = models.FloatField(default=0.0)
    card_fee_saved_usd = models.FloatField(default=0.0)
    kickoff_brief = models.TextField()
    flagged_risks = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "onboarding_runs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Onboarding: {self.business_name} ({self.created_at.strftime('%Y-%m-%d')})"

