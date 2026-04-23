from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import SupportRequest, SupportRequestEvent


FIRST_RESPONSE_TARGETS = {
    SupportRequest.PRIORITY_HIGH: timedelta(hours=8),
    SupportRequest.PRIORITY_NORMAL: timedelta(days=1),
    SupportRequest.PRIORITY_LOW: timedelta(days=2),
}


REQUEST_TYPE_HELP_TEXT = {
    SupportRequest.REQUEST_TYPE_VEHICLE_COMPLIANCE: (
        "Use this when a vehicle cannot be registered, insured, inspected, or shown as compliant."
    ),
    SupportRequest.REQUEST_TYPE_POLICY: (
        "Use this for policy issuance, renewal, cancellation, or policy status problems."
    ),
    SupportRequest.REQUEST_TYPE_PERMIT: (
        "Use this for LATRA, road license, route permit, inspection, or permit visibility issues."
    ),
    SupportRequest.REQUEST_TYPE_PAYMENT: (
        "Use this when payment confirmation, review, or activation is blocked."
    ),
    SupportRequest.REQUEST_TYPE_ACCESS: (
        "Use this for password resets, sign-in problems, or staff access questions."
    ),
    SupportRequest.REQUEST_TYPE_DATA_CORRECTION: (
        "Use this when a vehicle, policy, or permit record needs correction without deleting history."
    ),
    SupportRequest.REQUEST_TYPE_GENERAL: (
        "Use this when your issue does not fit one of the operational request types above."
    ),
}


def get_request_type_help_text():
    return REQUEST_TYPE_HELP_TEXT.copy()


def _clean_reference(value):
    return (value or '').strip()


def add_event(
    *,
    support_request,
    actor,
    event_type,
    message='',
    visibility=SupportRequestEvent.VISIBILITY_TENANT,
    from_status='',
    to_status='',
    previous_assignee=None,
    new_assignee=None,
):
    tenant = getattr(support_request, 'tenant', None)
    if tenant is None:
        raise ValidationError("Support request tenant is required.")

    return SupportRequestEvent.objects.create(
        tenant=tenant,
        support_request=support_request,
        event_type=event_type,
        visibility=visibility,
        message=(message or '').strip(),
        from_status=from_status or '',
        to_status=to_status or '',
        previous_assignee=previous_assignee,
        new_assignee=new_assignee,
        created_by=actor,
        updated_by=actor,
    )


@transaction.atomic
def create_support_request(
    *,
    tenant,
    actor,
    subject,
    message,
    priority,
    request_type,
    vehicle_registration_number='',
    policy_reference='',
    permit_reference='',
):
    ticket = SupportRequest.objects.create(
        tenant=tenant,
        subject=(subject or '').strip(),
        message=(message or '').strip(),
        priority=priority,
        request_type=request_type,
        vehicle_registration_number=_clean_reference(vehicle_registration_number),
        policy_reference=_clean_reference(policy_reference),
        permit_reference=_clean_reference(permit_reference),
        created_by=actor,
        updated_by=actor,
    )
    add_event(
        support_request=ticket,
        actor=actor,
        event_type=SupportRequestEvent.EVENT_CREATED,
        message=ticket.message,
        visibility=SupportRequestEvent.VISIBILITY_TENANT,
    )
    return ticket


@transaction.atomic
def update_support_request(
    *,
    support_request,
    actor,
    status,
    priority,
    assigned_to=None,
    tenant_message='',
    internal_note='',
    resolution_summary='',
):
    ticket = support_request
    previous_status = ticket.status
    previous_assignee = ticket.assigned_to
    tenant_message = (tenant_message or '').strip()
    internal_note = (internal_note or '').strip()
    resolution_summary = (resolution_summary or '').strip()

    if status == SupportRequest.STATUS_RESOLVED and not resolution_summary:
        raise ValidationError("Resolution summary is required when resolving a support request.")

    ticket.status = status
    ticket.priority = priority
    ticket.assigned_to = assigned_to
    ticket.updated_by = actor

    if status == SupportRequest.STATUS_RESOLVED:
        ticket.resolved_at = timezone.now()
        ticket.resolution_summary = resolution_summary
    elif previous_status == SupportRequest.STATUS_RESOLVED and status != SupportRequest.STATUS_RESOLVED:
        ticket.resolved_at = None
        ticket.resolution_summary = resolution_summary or ticket.resolution_summary
    elif resolution_summary:
        ticket.resolution_summary = resolution_summary

    ticket.save()

    if previous_assignee != assigned_to:
        add_event(
            support_request=ticket,
            actor=actor,
            event_type=SupportRequestEvent.EVENT_ASSIGNMENT_CHANGED,
            visibility=SupportRequestEvent.VISIBILITY_INTERNAL,
            previous_assignee=previous_assignee,
            new_assignee=assigned_to,
            message="Ticket assignment updated.",
        )

    if previous_status != status:
        event_type = SupportRequestEvent.EVENT_STATUS_CHANGED
        message = f"Status changed from {previous_status} to {status}."
        if status == SupportRequest.STATUS_RESOLVED:
            event_type = SupportRequestEvent.EVENT_RESOLVED
            message = resolution_summary
        elif previous_status == SupportRequest.STATUS_RESOLVED:
            event_type = SupportRequestEvent.EVENT_REOPENED
            message = "Support request reopened."
        add_event(
            support_request=ticket,
            actor=actor,
            event_type=event_type,
            visibility=SupportRequestEvent.VISIBILITY_TENANT,
            from_status=previous_status,
            to_status=status,
            message=message,
        )

    if tenant_message:
        add_event(
            support_request=ticket,
            actor=actor,
            event_type=SupportRequestEvent.EVENT_PUBLIC_REPLY,
            visibility=SupportRequestEvent.VISIBILITY_TENANT,
            message=tenant_message,
        )

    if internal_note:
        add_event(
            support_request=ticket,
            actor=actor,
            event_type=SupportRequestEvent.EVENT_INTERNAL_NOTE,
            visibility=SupportRequestEvent.VISIBILITY_INTERNAL,
            message=internal_note,
        )

    return ticket


def get_status_summary(*, queryset):
    return {
        'open': queryset.filter(status=SupportRequest.STATUS_OPEN).count(),
        'in_progress': queryset.filter(status=SupportRequest.STATUS_IN_PROGRESS).count(),
        'waiting_on_tenant': queryset.filter(status=SupportRequest.STATUS_WAITING_ON_TENANT).count(),
        'resolved': queryset.filter(status=SupportRequest.STATUS_RESOLVED).count(),
    }


def get_queue_counts(*, queryset):
    now = timezone.now()
    return {
        'all': queryset.count(),
        'unassigned': queryset.filter(assigned_to__isnull=True).count(),
        'high_priority': queryset.filter(priority=SupportRequest.PRIORITY_HIGH).exclude(
            status=SupportRequest.STATUS_RESOLVED
        ).count(),
        'waiting_on_tenant': queryset.filter(status=SupportRequest.STATUS_WAITING_ON_TENANT).count(),
        'aging': sum(1 for ticket in queryset if get_aging_state(ticket, now=now) != 'normal'),
        'resolved_recently': queryset.filter(
            status=SupportRequest.STATUS_RESOLVED,
            resolved_at__gte=now - timedelta(days=7),
        ).count(),
    }


def get_aging_state(ticket, *, now=None):
    now = now or timezone.now()
    if ticket.status == SupportRequest.STATUS_RESOLVED:
        return 'resolved'
    target = FIRST_RESPONSE_TARGETS.get(ticket.priority, FIRST_RESPONSE_TARGETS[SupportRequest.PRIORITY_NORMAL])
    age = now - ticket.created_at
    if age >= target:
        return 'overdue'
    if age >= target / 2:
        return 'warning'
    return 'normal'


def get_sla_label(ticket, *, now=None):
    state = get_aging_state(ticket, now=now)
    if state == 'resolved':
        return 'Resolved'
    if state == 'overdue':
        return 'Overdue'
    if state == 'warning':
        return 'Needs attention'
    return 'On track'

