from django.urls import path
from apps.core.views import (
    signup_endpoint,
    login_endpoint,
    logout_endpoint,
    current_user_endpoint,
    admin_metrics_endpoint,
    approve_application_endpoint,
    client_metrics_endpoint,
)

urlpatterns = [
    # Auth
    path("api/v1/auth/signup", signup_endpoint, name="signup"),
    path("api/v1/auth/login", login_endpoint, name="login"),
    path("api/v1/auth/logout", logout_endpoint, name="logout"),
    path("api/v1/auth/me", current_user_endpoint, name="current_user"),
    # Admin
    path("api/v1/admin/metrics", admin_metrics_endpoint, name="admin_metrics"),
    path("api/v1/admin/applications/<int:application_id>/approve", approve_application_endpoint, name="approve_application"),
    # Client
    path("api/v1/client/metrics", client_metrics_endpoint, name="client_metrics"),
]

