from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.core.models import User, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "tenant_id",
        "business_name",
        "vertical",
        "tier_name",
        "retainer_fee_usd",
        "included_minutes",
        "orchestrator",
        "created_at",
    )
    list_filter = ("vertical", "hipaa_baa_status", "shaken_stir_status")
    search_fields = ("tenant_id", "business_name", "escalation_phone")
    readonly_fields = ("created_at",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "full_name", "role", "status", "business_name", "vertical", "tenant", "created_at")
    list_filter = ("role", "status", "vertical")
    search_fields = ("email", "full_name", "business_name")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "business_name", "vertical", "tenant")}),
        ("Permissions", {"fields": ("role", "status", "is_active", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "status", "business_name", "vertical", "password"),
            },
        ),
    )

