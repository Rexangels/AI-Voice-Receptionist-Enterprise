from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, full_name="", **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, full_name="Superuser", **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "owner")
        extra_fields.setdefault("status", "ACTIVE")
        return self.create_user(email, password, full_name=full_name, **extra_fields)


class Tenant(models.Model):
    tenant_id = models.CharField(max_length=64, primary_key=True)
    business_name = models.CharField(max_length=255)
    vertical = models.CharField(max_length=64, default="dental")
    tier_name = models.CharField(max_length=128, default="Custom Built & Operated ($1M–$20M)")
    retainer_fee_usd = models.FloatField(default=1500.0)
    setup_fee_usd = models.FloatField(default=4500.0)
    included_minutes = models.IntegerField(default=1500)
    overage_rate_per_min_usd = models.FloatField(default=0.20)
    avg_ticket_usd = models.FloatField(default=450.0)
    close_rate = models.FloatField(default=0.35)
    escalation_phone = models.CharField(max_length=32, default="+15550123456")
    orchestrator = models.CharField(max_length=128, default="Retell AI + Telnyx SIP")
    hipaa_baa_status = models.CharField(max_length=128, default="Active (Self-Serve BAA)")
    shaken_stir_status = models.CharField(max_length=128, default="Level A Attested")
    a2p_10dlc_status = models.CharField(max_length=128, default="TCR Approved")
    supported_skills = models.TextField(
        default="implant_consultation,emergency_exam,emergency_crown_repair,routine_cleaning,dental_consultation,general_inquiry"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tenants"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.business_name} ({self.tenant_id})"


class User(AbstractUser):
    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("client", "Client"),
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("ACTIVE", "Active"),
        ("SUSPENDED", "Suspended"),
    )

    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=120)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="client")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="PENDING")
    business_name = models.CharField(max_length=150, blank=True)
    vertical = models.CharField(max_length=64, blank=True)
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.full_name} <{self.email}> ({self.role}/{self.status})"

