from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View


class TenantLoginView(LoginView):
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user

        # If tenant user, ensure tenant exists and is active
        if not getattr(user, 'is_super_admin', False):
            tenant = getattr(user, 'tenant', None)
            if not tenant or not tenant.is_active:
                messages.error(self.request, "Your organization's account is not active. Please contact support.")
                logout(self.request)
                return redirect('accounts:login')
        return response

    def get_success_url(self):
        user = self.request.user
        if getattr(user, 'is_super_admin', False):
            return reverse_lazy('super_admin:home')
        return reverse_lazy('dashboard:home')


class TenantLogoutView(View):
    """Logout view requiring POST for better security."""

    def post(self, request):
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect('accounts:login')

    def get(self, request):
        # Graceful fallback: redirect to login without logging out via GET
        messages.info(request, "Please use the Logout button to sign out.")
        return redirect('dashboard:home' if request.user.is_authenticated else 'accounts:login')
