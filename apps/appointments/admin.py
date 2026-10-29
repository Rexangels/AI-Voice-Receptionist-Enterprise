from django.contrib import admin
from apps.appointments.models import AppointmentSlotLock


@admin.register(AppointmentSlotLock)
class AppointmentSlotLockAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "resource_id",
        "slot_iso",
        "caller_name",
        "caller_phone",
        "service_type",
        "status",
        "verbal_confirmed",
        "created_at",
    )
    list_filter = ("status", "tenant", "verbal_confirmed")
    search_fields = ("caller_name", "caller_phone", "idempotency_key", "slot_iso")
    readonly_fields = ("idempotency_key", "created_at")

