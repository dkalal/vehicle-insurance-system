from django.urls import path
from .views import (
    TenantLoginView,
    TenantLogoutView,
    ForcePasswordChangeView,
    StaffPasswordForceResetView,
    UserPasswordChangeView,
    ProfileSettingsView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", TenantLoginView.as_view(), name="login"),
    path("logout/", TenantLogoutView.as_view(), name="logout"),
    path("password/change/", ForcePasswordChangeView.as_view(), name="force_password_change"),
    path("password/change/self/", UserPasswordChangeView.as_view(), name="change_password"),
    path("staff/<int:user_pk>/force-reset-password/", StaffPasswordForceResetView.as_view(), name="staff_force_reset_password"),
    path("profile/", ProfileSettingsView.as_view(), name="profile_settings"),
]
