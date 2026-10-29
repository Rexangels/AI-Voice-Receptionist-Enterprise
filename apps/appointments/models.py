from django.db import models
from apps.core.models import Tenant


class AppointmentSlotLock(models.Model):
    STATUS_CHOICES = (
        ("CONFIRMED", "Confirmed"),
        ("COMPLETED", "Completed"),
        ("RESCHEDULED", "Rescheduled"),
        ("NO_SHOW", "No Show"),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="slot_locks")
    resource_id = models.CharField(max_length=64, default="chair_1")
    slot_iso = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=255, unique=True)
    caller_name = models.CharField(max_length=120)
    caller_phone = models.CharField(max_length=32)
    service_type = models.CharField(max_length=120)
    duration_minutes = models.IntegerField(default=60)
    verbal_confirmed = models.BooleanField(default=True)
    skill_verified = models.BooleanField(default=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="CONFIRMED")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appointment_slot_locks"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "resource_id", "slot_iso"],
                name="uq_tenant_resource_slot",
            )
        ]

    def __str__(self):
        return f"{self.tenant_id} | {self.resource_id} | {self.slot_iso} ({self.caller_name})"

