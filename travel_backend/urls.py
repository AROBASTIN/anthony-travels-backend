"""
URL configuration for travel_backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def root_view(request):
    """Root URL — confirms API is online."""
    return JsonResponse({
        'service': 'Anthony Travels API',
        'status': 'online',
        'version': '1.0.0',
        'health_check': '/api/health',
        'docs': 'All endpoints are prefixed with /api/',
    })

urlpatterns = [
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

# Serve uploaded media files (dev only; Vercel filesystem is ephemeral)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
