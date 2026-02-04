from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('notifications/', views.NotificationCenterView.as_view(), name='center'),
    path('api/notifications/', views.NotificationListAPIView.as_view(), name='api_list'),
    path('api/notifications/count/', views.NotificationCountAPIView.as_view(), name='api_count'),
    path('api/notifications/mark-read/', views.NotificationMarkReadAPIView.as_view(), name='api_mark_all_read'),
    path('api/notifications/<uuid:notification_id>/mark-read/', views.NotificationMarkReadAPIView.as_view(), name='api_mark_read'),
    path('api/notifications/preferences/', views.NotificationPreferencesAPIView.as_view(), name='api_preferences'),
]