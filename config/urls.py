from django.contrib import admin
from django.urls import include, path

from django.conf import settings
from django.conf.urls.static import static

from apps.accounts.views import HomeView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("stores/", include("apps.stores.urls")),
    path("inspections/", include("apps.inspections.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("", HomeView.as_view(), name="home"),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )