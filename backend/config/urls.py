from django.contrib import admin
from django.urls import path, re_path

from predictor import views, waivers

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", views.health),
    path("api/summary", views.summary),
    path("api/predictions", views.predictions),
    path("api/accuracy", views.accuracy),
    path("api/players/<str:player_id>", views.player_detail),
    path("api/waivers", waivers.waivers),
    re_path(r"^(?!api/|admin/|static/).*$", views.spa),
]
