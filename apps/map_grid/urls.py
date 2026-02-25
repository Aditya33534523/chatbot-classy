from django.urls import path
from . import views

urlpatterns = [
    path('locations', views.all_locations),
    path('hospitals', views.nearby_hospitals),
    path('pharmacies', views.nearby_pharmacies),
    path('emergency', views.emergency_hospitals),
    path('search', views.search_facilities),
    path('facility/<str:facility_id>', views.facility_detail),
    path('send-directions', views.send_directions_whatsapp),
]
