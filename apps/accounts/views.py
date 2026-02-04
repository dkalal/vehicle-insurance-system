from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from apps.accounts.forms import ForcePasswordChangeForm, UserPasswordChangeForm, ProfileUpdateForm
from apps.accounts.permissions import TenantRoleRequiredMixin
from apps.core.services import onboarding_service
from apps.accounts.services import password_reset_service, profile_service


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
        tenant = getattr(user, 'tenant', None)
        if tenant and getattr(user, 'role', None) in ('admin', 'manager'):
            # Only redirect to onboarding for brand-new tenants with no state yet.
            if onboarding_service.should_redirect_to_onboarding_on_login(tenant=tenant):
                return reverse_lazy('dashboard:onboarding_welcome')
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


class ForcePasswordChangeView(LoginRequiredMixin, FormView):
    template_name = 'accounts/force_password_change.html'
    form_class = ForcePasswordChangeForm
    success_url = reverse_lazy('dashboard:home')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        new_password = form.cleaned_data['new_password1']
        user.set_password(new_password)
        if hasattr(user, 'must_change_password'):
            user.must_change_password = False
        if hasattr(user, 'password_last_reset_at'):
            from django.utils import timezone
            user.password_last_reset_at = timezone.now()
        user.save()
        update_session_auth_hash(self.request, user)
        messages.success(self.request, 'Your password has been updated.')
        return super().form_valid(form)


class ProfileSettingsView(LoginRequiredMixin, FormView):
    template_name = 'accounts/profile_settings.html'
    form_class = ProfileUpdateForm
    success_url = reverse_lazy('dashboard:home')

    def get_initial(self):
        user = self.request.user
        return {
            'first_name': getattr(user, 'first_name', ''),
            'last_name': getattr(user, 'last_name', ''),
            'email': getattr(user, 'email', ''),
            'phone_number': getattr(user, 'phone_number', ''),
        }

    def form_valid(self, form):
        user = self.request.user
        try:
            profile_service.update_profile(
                user=user,
                first_name=form.cleaned_data.get('first_name', ''),
                last_name=form.cleaned_data.get('last_name', ''),
                email=form.cleaned_data.get('email', ''),
                phone_number=form.cleaned_data.get('phone_number', ''),
            )
        except ValidationError as exc:
            # Surface validation errors back to the form
            non_field_errors = '\n'.join(exc.messages) if hasattr(exc, 'messages') else str(exc)
            form.add_error(None, non_field_errors)
            return self.form_invalid(form)

        messages.success(self.request, 'Your profile has been updated.')
        return super().form_valid(form)


class UserPasswordChangeView(LoginRequiredMixin, FormView):
    template_name = 'accounts/change_password.html'
    form_class = UserPasswordChangeForm
    success_url = reverse_lazy('dashboard:home')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        new_password = form.cleaned_data['new_password1']
        user.set_password(new_password)
        if hasattr(user, 'must_change_password'):
            user.must_change_password = False
        if hasattr(user, 'password_last_reset_at'):
            from django.utils import timezone
            user.password_last_reset_at = timezone.now()
        user.save()
        update_session_auth_hash(self.request, user)
        messages.success(self.request, 'Your password has been updated.')
        return super().form_valid(form)


class StaffPasswordForceResetView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin',)

    def post(self, request, user_pk):
        User = get_user_model()
        target = get_object_or_404(
            User,
            pk=user_pk,
            tenant=request.tenant,
            is_super_admin=False,
        )
        reason = request.POST.get('reason', '')
        try:
            temp_password = password_reset_service.force_reset_password(
                actor=request.user,
                target_user=target,
                reason=reason,
                ip_address=request.META.get('REMOTE_ADDR'),
            )
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            display_name = target.get_full_name() or target.username
            messages.success(
                request,
                f'Password reset for {display_name}. Temporary password: {temp_password}. '
                'Ask the user to change it after login.',
                extra_tags='no-autohide'
            )
        return redirect('dashboard:staff_list')
