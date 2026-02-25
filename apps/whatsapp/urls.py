from django.urls import path
from . import views

urlpatterns = [
    path('send-message', views.send_message),
    path('send-template', views.send_template),
    path('medication-reminder', views.medication_reminder),
    path('emergency-alert', views.emergency_alert),
    path('hospital-directions', views.hospital_directions),
    path('broadcast', views.broadcast),
    path('session-status/<str:phone_number>', views.session_status),
    path('webhook', views.webhook),
]
