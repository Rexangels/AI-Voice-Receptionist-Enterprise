from django.urls import path
from apps.voice_telephony.views import (
    vapi_webhook_endpoint,
    warm_transfer_hold_endpoint,
    staff_whisper_endpoint,
    warm_transfer_preview_endpoint,
)

urlpatterns = [
    path("api/v1/voice/vapi-webhook", vapi_webhook_endpoint, name="vapi_webhook"),
    path("api/v1/telephony/warm-transfer-hold", warm_transfer_hold_endpoint, name="warm_transfer_hold"),
    path("api/v1/telephony/staff-whisper", staff_whisper_endpoint, name="staff_whisper"),
    path("api/v1/telephony/warm-transfer-preview", warm_transfer_preview_endpoint, name="warm_transfer_preview"),
]

