from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class FieldDefinition(models.Model):
    """
    Definition of a dynamic field for an entity (Customer, Vehicle, Policy).

    Enforces structure and queryability via explicit types and per-tenant scoping.
    """

    ENTITY_CUSTOMER = 'customer'
    ENTITY_VEHICLE = 'vehicle'
    ENTITY_POLICY = 'policy'

    ENTITY_CHOICES = [
        (ENTITY_CUSTOMER, 'Customer'),
        (ENTITY_VEHICLE, 'Vehicle'),
        (ENTITY_POLICY, 'Policy'),
    ]

    TYPE_TEXT = 'text'
    TYPE_NUMBER = 'number'
    TYPE_DATE = 'date'
    TYPE_BOOLEAN = 'boolean'
    TYPE_DROPDOWN = 'dropdown'

    TYPE_CHOICES = [
        (TYPE_TEXT, 'Text'),
        (TYPE_NUMBER, 'Number'),
        (TYPE_DATE, 'Date'),
        (TYPE_BOOLEAN, 'Boolean'),
        (TYPE_DROPDOWN, 'Dropdown'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.PROTECT, related_name='field_definitions', db_index=True
    )
    entity_type = models.CharField(max_length=20, choices=ENTITY_CHOICES, db_index=True)
    name = models.CharField(max_length=255, help_text='Human-readable label')
    key = models.SlugField(max_length=100, help_text='Machine key, unique per tenant+entity')
    data_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    order = models.PositiveIntegerField(default=0, help_text='Display order')
    # For dropdown options, store list of strings
    options = models.JSONField(default=list, blank=True, help_text='Allowed options for dropdown')

    class Meta:
        unique_together = (
            ('tenant', 'entity_type', 'key'),
        )
        ordering = ['tenant_id', 'entity_type', 'order', 'name']
        indexes = [
            models.Index(fields=['tenant', 'entity_type', 'is_active']),
            models.Index(fields=['tenant', 'entity_type', 'key']),
        ]

    def __str__(self):
        return f"{self.tenant_id}:{self.entity_type}:{self.name}"

    def clean(self):
        super().clean()
        if self.data_type == self.TYPE_DROPDOWN and not isinstance(self.options, list):
            raise ValidationError({'options': 'Dropdown options must be a list.'})
        if self.data_type != self.TYPE_DROPDOWN and self.options:
            raise ValidationError({'options': 'Options applicable only for dropdown type.'})


class FieldValue(models.Model):
    """
    Concrete value for a FieldDefinition attached to a specific entity instance.

    Uses GenericForeignKey to support Customer, Vehicle, Policy while preserving queryability
    via indexed content_type/object_id and per-type value columns.
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.PROTECT, related_name='field_values', db_index=True
    )
    definition = models.ForeignKey(FieldDefinition, on_delete=models.PROTECT, related_name='values')

    # Generic relation to target entity
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Typed value columns (only one should be set depending on definition.data_type)
    text_value = models.TextField(blank=True)
    number_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    date_value = models.DateField(null=True, blank=True)
    bool_value = models.BooleanField(null=True, blank=True)
    option_value = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['tenant_id', 'definition_id', 'id']
        indexes = [
            models.Index(fields=['tenant', 'definition']),
            models.Index(fields=['tenant', 'content_type', 'object_id']),
        ]
        unique_together = (
            ('tenant', 'definition', 'content_type', 'object_id'),
        )

    def __str__(self):
        return f"{self.definition.key}={self.value_repr()}"

    def clean(self):
        super().clean()
        # Tenant alignment
        if self.definition and self.tenant_id and self.definition.tenant_id != self.tenant_id:
            raise ValidationError({'tenant': 'Tenant mismatch with field definition.'})

        # Ensure only the appropriate value field is used based on the definition type
        dt = getattr(self.definition, 'data_type', None)
        values = {
            'text': bool(self.text_value),
            'number': self.number_value is not None,
            'date': self.date_value is not None,
            'boolean': self.bool_value is not None,
            'dropdown': bool(self.option_value),
        }
        if dt and sum(1 for k, v in values.items() if v) > 1:
            raise ValidationError('Only one typed value must be provided.')
        if dt == FieldDefinition.TYPE_TEXT and not values['text']:
            if self.definition.is_required:
                raise ValidationError({'text_value': 'This field is required.'})
        elif dt == FieldDefinition.TYPE_NUMBER and not values['number']:
            if self.definition.is_required:
                raise ValidationError({'number_value': 'This field is required.'})
        elif dt == FieldDefinition.TYPE_DATE and not values['date']:
            if self.definition.is_required:
                raise ValidationError({'date_value': 'This field is required.'})
        elif dt == FieldDefinition.TYPE_BOOLEAN and not values['boolean']:
            if self.definition.is_required:
                raise ValidationError({'bool_value': 'This field is required.'})
        elif dt == FieldDefinition.TYPE_DROPDOWN:
            if not values['dropdown'] and self.definition.is_required:
                raise ValidationError({'option_value': 'This field is required.'})
            if self.option_value and self.definition.options and self.option_value not in self.definition.options:
                raise ValidationError({'option_value': 'Invalid option.'})

    def value_repr(self):
        if self.definition.data_type == FieldDefinition.TYPE_TEXT:
            return self.text_value
        if self.definition.data_type == FieldDefinition.TYPE_NUMBER:
            return str(self.number_value)
        if self.definition.data_type == FieldDefinition.TYPE_DATE:
            return str(self.date_value)
        if self.definition.data_type == FieldDefinition.TYPE_BOOLEAN:
            return str(self.bool_value)
        if self.definition.data_type == FieldDefinition.TYPE_DROPDOWN:
            return self.option_value
        return ''
