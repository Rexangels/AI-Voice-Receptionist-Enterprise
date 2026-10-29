from django.urls import path
from apps.telemetry.views import (
    system_state_endpoint,
    roi_report_endpoint,
    stress_test_endpoint,
    pricing_calculator_endpoint,
    onboard_client_endpoint,
    generate_gtm_assets_endpoint,
)

urlpatterns = [
    path("api/v1/voice/state", system_state_endpoint, name="system_state"),
    path("api/v1/voice/roi-report/<str:tenant_id>", roi_report_endpoint, name="roi_report"),
    path("api/v1/voice/run-stress-test", stress_test_endpoint, name="stress_test"),
    path("api/v1/voice/pricing-calculator", pricing_calculator_endpoint, name="pricing_calculator"),
    path("api/v1/agency/onboard-client", onboard_client_endpoint, name="onboard_client"),
    path("api/v1/agency/generate-gtm-assets", generate_gtm_assets_endpoint, name="generate_gtm_assets"),
]

