"""文件管理模块路由。挂载前缀 /files/（见 config/urls.py）。"""

from django.urls import path

from . import views

app_name = "files"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("upload/", views.upload_view, name="upload"),
    path("<int:pk>/download/", views.download_view, name="download"),
    path("<int:pk>/delete/", views.delete_view, name="delete"),
]
