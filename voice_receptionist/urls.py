from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import (
    health_check,
    index_page,
    login_page,
    signup_page,
    admin_page,
    client_page,
    public_asset,
)

urlpatterns = [
    # Built-in Django Admin Interface
    path("django-admin/", admin.site.urls),

    # Health Checks
    path("health", health_check, name="health_check"),
    path("api/health", health_check, name="api_health_check"),

    # Application APIs
    path("", include("apps.core.urls")),
    path("", include("apps.appointments.urls")),
    path("", include("apps.voice_telephony.urls")),
    path("", include("apps.telemetry.urls")),

    # Frontend UI Pages
    path("", index_page, name="index"),
    path("login", login_page, name="login_page"),
    path("signup", signup_page, name="signup_page"),
    path("admin", admin_page, name="admin_page"),
    path("client", client_page, name="client_page"),

    # Public static / asset downloads
    re_path(r"^public/assets/(?P<path>.*)$", public_asset, name="public_asset"),
    re_path(r"^assets/(?P<path>.*)$", public_asset, name="asset_fallback"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

