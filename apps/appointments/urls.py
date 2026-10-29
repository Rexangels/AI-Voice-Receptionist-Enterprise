from django.urls import path
from apps.appointments.views import (
    book_direct_endpoint,
    update_booking_status_endpoint,
    release_slot_endpoint,
)

urlpatterns = [
    path("api/v1/voice/book-direct", book_direct_endpoint, name="book_direct"),
    path("api/v1/voice/update-booking-status", update_booking_status_endpoint, name="update_booking_status"),
    path("api/v1/voice/release-slot", release_slot_endpoint, name="release_slot"),
]

