from django.contrib import admin
from django.urls import path, re_path

from predictor import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", views.health),
    path("api/summary", views.summary),
    path("api/predictions", views.predictions),
    path("api/players/<str:player_id>", views.player_detail),
    re_path(r"^(?!api/|admin/|static/).*$", views.spa),
]
