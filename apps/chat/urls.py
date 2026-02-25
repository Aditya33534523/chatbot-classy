from django.urls import path
from . import views

urlpatterns = [
    path('init', views.init_chat),
    path('message', views.message),
    path('query', views.query),
    path('drug-search', views.drug_search),
    path('emergency-drugs', views.emergency_drugs),
    path('quick-info/<str:drug_name>', views.quick_info),
    path('history', views.history),
    path('clear-history', views.clear_history),
    path('history/<str:user_email>', views.user_history),
    path('conversation/<str:session_id>', views.conversation_detail),
]
