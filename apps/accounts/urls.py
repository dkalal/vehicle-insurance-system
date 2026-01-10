from django.urls import path
from .views import TenantLoginView, TenantLogoutView

app_name = "accounts"

urlpatterns = [
    path("login/", TenantLoginView.as_view(), name="login"),
    path("logout/", TenantLogoutView.as_view(), name="logout"),
]
