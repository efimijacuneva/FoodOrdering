from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from orders import views as order_views


def health_check(request):
    """Lightweight liveness probe — no DB query, no auth required."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path('health/', health_check, name='health'),
    path('django-admin/', admin.site.urls),
    path('accounts/login/', order_views.login_view, name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('orders.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
