from django.contrib import admin
from apps.compliance.models import SuppressionRegistry


@admin.register(SuppressionRegistry)
class SuppressionRegistryAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "phone_number", "revocation_phrase", "channel", "revoked_at")
    list_filter = ("channel", "tenant")
    search_fields = ("phone_number", "revocation_phrase")
    readonly_fields = ("revoked_at",)

