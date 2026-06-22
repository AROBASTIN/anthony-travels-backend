from django.urls import path
from . import views

urlpatterns = [
    # ── Health check ──────────────────────────────────────────
    path('health', views.health_check_view, name='health_check'),

    # ── Auth endpoints ────────────────────────────────────────
    path('auth/register', views.register_view, name='register'),
    path('auth/login', views.login_view, name='login'),
    path('auth/refresh', views.refresh_token_view, name='refresh_token'),
    path('auth/profile', views.profile_view, name='profile'),

    # ── Vehicle endpoints ─────────────────────────────────────
    path('vehicles', views.vehicles_list_view, name='vehicles_list'),
    path('vehicles/<str:vehicle_id>', views.vehicle_detail_view, name='vehicle_detail'),

    # ── Driver endpoints ──────────────────────────────────────
    path('drivers', views.drivers_list_view, name='drivers_list'),
    path('drivers/<str:driver_id>/documents', views.driver_document_view, name='driver_document'),

    # ── Booking endpoints ─────────────────────────────────────
    path('bookings', views.bookings_list_view, name='bookings_list'),
    path('bookings/<str:booking_id>/status', views.booking_status_view, name='booking_status'),

    # ── Payment endpoints ─────────────────────────────────────
    path('payments/checkout', views.payments_checkout_view, name='payments_checkout'),

    # ── Reviews and FAQs ──────────────────────────────────────
    path('reviews', views.reviews_view, name='reviews'),
    path('faqs', views.faqs_view, name='faqs'),

    # ── Fuel Prices ───────────────────────────────────────────
    path('fuel-prices', views.fuel_prices_view, name='fuel_prices'),

    # ── Dashboard ─────────────────────────────────────────────
    path('dashboards/stats', views.dashboard_stats_view, name='dashboard_stats'),

    # ── Admin Super Control endpoints ─────────────────────────
    path('admin/pricing', views.admin_pricing_view, name='admin_pricing'),
    path('admin/content', views.admin_content_view, name='admin_content'),
    path('admin/users', views.admin_users_view, name='admin_users'),
    path('admin/users/<str:user_id>', views.admin_user_detail_view, name='admin_user_detail'),
    path('admin/drivers', views.admin_drivers_view, name='admin_drivers'),
    path('admin/drivers/<str:driver_id>', views.admin_driver_detail_view, name='admin_driver_detail'),
    path('admin/bookings/<str:booking_id>', views.admin_booking_detail_view, name='admin_booking_detail'),
    path('admin/vehicles/<str:vehicle_id>/approve', views.admin_vehicle_approve_view, name='admin_vehicle_approve'),

    # ── KYC Verification System ──────────────────────────────────
    path('kyc/status', views.kyc_status_view, name='kyc_status'),
    path('kyc/upload', views.kyc_upload_view, name='kyc_upload'),
    path('admin/kyc/requests', views.admin_kyc_list_view, name='admin_kyc_list'),
    path('admin/kyc/requests/<str:request_id>/action', views.admin_kyc_action_view, name='admin_kyc_action'),

    # ── Enquiry / Booking Workflow ────────────────────────────────
    path('enquiries', views.enquiries_view, name='enquiries_list'),
    path('enquiries/<str:enquiry_id>', views.enquiry_detail_view, name='enquiry_detail'),
]

