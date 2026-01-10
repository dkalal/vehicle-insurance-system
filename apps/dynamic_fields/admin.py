from django.contrib import admin
from .models import FieldDefinition, FieldValue


@admin.register(FieldDefinition)
class FieldDefinitionAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'entity_type', 'name', 'key', 'data_type', 'is_required', 'is_active', 'order'
    ]
    list_filter = ['tenant', 'entity_type', 'data_type', 'is_active']
    search_fields = ['name', 'key']
    ordering = ['tenant', 'entity_type', 'order', 'name']


@admin.register(FieldValue)
class FieldValueAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'definition', 'content_type', 'object_id', 'text_value', 'number_value',
        'date_value', 'bool_value', 'option_value'
    ]
    list_filter = ['tenant', 'definition__entity_type', 'definition__data_type']
    search_fields = ['definition__key', 'option_value']
    ordering = ['tenant', 'definition', 'id']
