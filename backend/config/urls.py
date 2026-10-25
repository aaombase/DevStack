from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("projects.urls")),
    path("api/", include("tasks.urls")),
    path("api/", include("analytics.urls")),
    path("api/integrations/", include("integrations.urls")),
]
