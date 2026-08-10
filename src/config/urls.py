from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)

from api.schema import ADMIN_SETTINGS, FRONTEND_SETTINGS
from api.views_health import HealthCheckView

# Three documents over the same routes: the whole API, the storefront subset
# a frontend developer needs, and the staff-only subset.
schema_urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"),
         name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"),
         name="redoc"),

    path("schema/frontend/",
         SpectacularAPIView.as_view(custom_settings=FRONTEND_SETTINGS),
         name="schema-frontend"),
    path("docs/frontend/",
         SpectacularSwaggerView.as_view(
             url_name="schema-frontend",
             title=FRONTEND_SETTINGS["TITLE"]),
         name="swagger-ui-frontend"),
    path("redoc/frontend/",
         SpectacularRedocView.as_view(
             url_name="schema-frontend",
             title=FRONTEND_SETTINGS["TITLE"]),
         name="redoc-frontend"),

    path("schema/admin/",
         SpectacularAPIView.as_view(custom_settings=ADMIN_SETTINGS),
         name="schema-admin"),
    path("docs/admin/",
         SpectacularSwaggerView.as_view(
             url_name="schema-admin", title=ADMIN_SETTINGS["TITLE"]),
         name="swagger-ui-admin"),
    path("redoc/admin/",
         SpectacularRedocView.as_view(
             url_name="schema-admin", title=ADMIN_SETTINGS["TITLE"]),
         name="redoc-admin"),
]

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html")),
    path("healthz/", HealthCheckView.as_view(), name="health"),

    path("api/v1/", include("api.urls")),
    path("api/", include(schema_urlpatterns)),

    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += [
        *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
        *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    ]
