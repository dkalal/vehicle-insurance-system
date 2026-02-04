# Development Guidelines

## Code Quality Standards

### Import Organization
- **Django imports first**: Core Django modules imported before third-party
- **Third-party imports**: External packages grouped separately
- **Local imports**: Project-specific imports last
- **Relative imports**: Use relative imports for same-app modules
- **Import grouping**: Separate groups with blank lines

```python
# Django core
from django.db import models
from django.core.exceptions import ValidationError

# Third-party
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog

# Local
from .base import BaseModel
from apps.core.services import customer_service
```

### Naming Conventions
- **Models**: PascalCase (e.g., `Policy`, `VehiclePermit`)
- **Variables/Functions**: snake_case (e.g., `policy_number`, `get_total_paid`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `STATUS_ACTIVE`, `REQUIRED_COLUMNS`)
- **Private methods**: Leading underscore (e.g., `_norm`, `_validate_required`)
- **Class methods**: Descriptive names (e.g., `generate_policy_number`, `can_activate`)

### Documentation Standards
- **Docstrings**: Triple quotes for all classes and methods
- **Method documentation**: Include Args, Returns, Raises sections
- **Business rules**: Document critical business logic in docstrings
- **Inline comments**: Explain complex logic and business rules

```python
def can_activate(self):
    """
    Check if policy can be activated.
    
    Requirements:
    1. Status is pending_payment or draft
    2. Fully paid
    3. Vehicle doesn't have another active policy
    
    Returns:
        Tuple: (can_activate, reason)
    """
```

## Architectural Patterns

### Service Layer Pattern
- **Business logic**: All business logic encapsulated in service modules
- **View responsibility**: Views handle HTTP concerns, delegate to services
- **Service functions**: Named with action verbs (e.g., `create_customer`, `import_vehicles_from_csv`)
- **Transaction management**: Services handle database transactions

```python
# Service layer example
def create_policy(*, created_by, vehicle, start_date, end_date, premium_amount, **kwargs):
    """Create a new policy with validation."""
    # Business logic here
    return policy

# View delegates to service
def form_valid(self, form):
    policy = policy_service.create_policy(
        created_by=self.request.user,
        **form.cleaned_data
    )
```

### Multi-Tenant Architecture
- **Tenant scoping**: All business models automatically scoped to tenant
- **Tenant context**: Available via `request.tenant` in views
- **Manager usage**: Use tenant-aware managers for all queries
- **Access control**: Verify tenant access before operations

```python
# Tenant-aware querying
customers = Customer.objects.all()  # Automatically scoped
policies = Policy.objects.filter(vehicle__vehicle_type__in=allowed)

# Tenant context usage
tenant = self.request.tenant
settings_value = tenant.get_setting('expiry_reminder_days', 30)
```

### Permission and Access Control
- **Mixin usage**: Use `TenantUserRequiredMixin`, `TenantRoleRequiredMixin`
- **Role-based access**: Define `allowed_roles` on views
- **Vehicle access**: Use `vehicle_access_service` for vehicle-specific permissions
- **Service-level checks**: Validate access in service layer

```python
class PolicyCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    
    def form_valid(self, form):
        vehicle_access_service.ensure_user_can_access_vehicle(
            user=self.request.user, 
            vehicle=form.cleaned_data['vehicle']
        )
```

## Data Handling Patterns

### Model Design
- **Base model inheritance**: All models inherit from `BaseModel`
- **Soft deletes**: Use `deleted_at` field, never hard delete business data
- **History tracking**: Use `HistoricalRecords` for audit trails
- **Constraints**: Define database constraints for business rules
- **Indexes**: Add indexes for tenant_id, foreign keys, and search fields

```python
class Policy(BaseModel):
    history = HistoricalRecords()
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F('start_date')),
                name='end_date_after_start_date'
            ),
        ]
```

### Validation Patterns
- **Model validation**: Implement `clean()` method for business rules
- **Service validation**: Validate in service layer before database operations
- **Form validation**: Use Django forms for user input validation
- **Error handling**: Catch `ValidationError` and map to form errors

```python
def clean(self):
    """Validate policy before saving."""
    super().clean()
    if self.status == self.STATUS_ACTIVE and self.vehicle_id:
        # Check business rules
        if active_policies.exists():
            raise ValidationError({
                'vehicle': 'Only one active policy per vehicle is allowed.'
            })
```

### Query Optimization
- **Select related**: Use `select_related()` for foreign key relationships
- **Prefetch related**: Use `prefetch_related()` for reverse relationships
- **Only fields**: Use `only()` to limit fields in list views
- **Bulk operations**: Use bulk methods for large datasets

```python
# Optimized queries
qs = (
    Policy.objects
    .select_related('vehicle', 'vehicle__owner')
    .prefetch_related('payments')
    .only('policy_number', 'status', 'start_date')
)
```

## Error Handling Patterns

### Exception Management
- **Specific exceptions**: Catch specific exception types
- **Error mapping**: Map service exceptions to form errors
- **User feedback**: Provide meaningful error messages
- **Logging**: Log errors for debugging and monitoring

```python
try:
    policy = policy_service.create_policy(**data)
except ValidationError as exc:
    if isinstance(exc.message_dict, dict):
        for field, errs in exc.message_dict.items():
            for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                form.add_error(field if field in form.fields else None, msg)
    return self.form_invalid(form)
```

### Data Import Error Handling
- **Row-level errors**: Track errors per row in CSV imports
- **Validation aggregation**: Collect all validation errors before processing
- **Partial success**: Allow partial imports with error reporting
- **Transaction safety**: Use transactions for data consistency

```python
def import_vehicles_from_csv(*, tenant, user, file_obj):
    errors = []
    created = 0
    
    for row_num, row in enumerate(reader, start=2):
        row_errors = _validate_required(row, row_num)
        if row_errors:
            errors.append({'row': row_num, 'errors': row_errors})
            continue
```

## UI/UX Patterns

### Form Handling
- **Dynamic fields**: Support for tenant-specific custom fields
- **Validation feedback**: Show validation errors clearly
- **Success messages**: Provide confirmation for successful operations
- **Progressive disclosure**: Show relevant fields based on context

```python
def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx['df_defs'] = FieldDefinition.objects.filter(
        tenant=self.request.tenant,
        entity_type=FieldDefinition.ENTITY_CUSTOMER,
        is_active=True,
    ).order_by('order', 'name')
```

### List View Patterns
- **Pagination**: Use consistent pagination (25 items per page)
- **Search functionality**: Implement search across relevant fields
- **Filtering**: Support status and type filtering
- **Export capabilities**: Provide CSV, XLSX, PDF export options

```python
def get_queryset(self):
    qs = Model.objects.select_related('related_field').order_by('-created_at')
    q = (self.request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(field1__icontains=q) | Q(field2__icontains=q))
    return qs
```

## Performance Patterns

### Caching Strategy
- **Query caching**: Cache expensive database queries
- **Session caching**: Use Redis for session storage
- **Metrics caching**: Cache dashboard metrics for performance
- **Cache invalidation**: Implement proper cache invalidation

```python
# Cache usage example
metrics = cache.get('performance_metrics')
if not metrics:
    metrics = calculate_metrics()
    cache.set('performance_metrics', metrics, 300)
```

### Background Processing
- **Celery tasks**: Use for heavy operations and notifications
- **Periodic tasks**: Schedule recurring operations
- **Error handling**: Implement retry logic for failed tasks
- **Monitoring**: Log task execution and failures

```python
@shared_task
def send_expiry_reminders():
    """Send policy expiry reminder notifications."""
    # Background task implementation
```

## Security Patterns

### Authentication and Authorization
- **Session security**: Implement session rotation and expiry
- **Rate limiting**: Protect against brute force attacks
- **CSRF protection**: Use CSRF tokens on all forms
- **Permission checks**: Verify permissions at multiple layers

### Data Protection
- **Tenant isolation**: Ensure complete data separation
- **Audit logging**: Track all data modifications
- **Soft deletes**: Preserve data for compliance
- **Input validation**: Sanitize all user inputs

## Testing Patterns

### Test Organization
- **Factory pattern**: Use Factory Boy for test data generation
- **Service testing**: Test business logic in service layer
- **Integration testing**: Test complete workflows
- **Permission testing**: Verify access control

### Test Data Management
- **Tenant isolation**: Test multi-tenant scenarios
- **Clean state**: Ensure tests don't affect each other
- **Realistic data**: Use representative test data
- **Edge cases**: Test boundary conditions

## Code Review Standards

### Review Checklist
- **Business rules**: Verify business logic correctness
- **Security**: Check for security vulnerabilities
- **Performance**: Review query efficiency
- **Error handling**: Ensure proper exception handling
- **Documentation**: Verify adequate documentation

### Quality Gates
- **No hardcoded values**: Use constants or configuration
- **Proper logging**: Include appropriate logging statements
- **Transaction safety**: Ensure data consistency
- **Backward compatibility**: Maintain API compatibility