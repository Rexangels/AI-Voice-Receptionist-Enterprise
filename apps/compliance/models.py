from django.db import models
from apps.core.models import Tenant


class SuppressionRegistry(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="suppressions")
    phone_number = models.CharField(max_length=32)
    revocation_phrase = models.CharField(max_length=255, blank=True, null=True)
    channel = models.CharField(max_length=32, default="voice")
    revoked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "suppression_registry"
        ordering = ["-revoked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "phone_number"],
                name="uq_tenant_phone_suppression",
            )
        ]

    def __str__(self):
        return f"{self.tenant_id} | {self.phone_number} (Revoked: {self.revocation_phrase})"

