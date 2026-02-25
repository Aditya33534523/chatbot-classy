from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.chat.views import index_view

urlpatterns = [
    path('', index_view, name='index'),
    path('api/chat/', include('apps.chat.urls')),
    path('api/map/', include('apps.map_grid.urls')),
    path('api/whatsapp/', include('apps.whatsapp.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
