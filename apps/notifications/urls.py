"""消息通知模块路由。挂载前缀 /notifications/（见 config/urls.py）。"""

from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("read-all/", views.mark_all_read_view, name="mark_all_read"),
    path("<int:pk>/", views.detail_view, name="detail"),
    path("<int:pk>/read/", views.mark_read_view, name="mark_read"),
    path("<int:pk>/delete/", views.delete_view, name="delete"),
]
