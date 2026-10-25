from django.urls import path

from .views import CommitListView, SyncView, WebhookView

urlpatterns = [
    path("projects/<int:project_id>/sync/", SyncView.as_view()),
    path("projects/<int:project_id>/commits/", CommitListView.as_view()),
    path("projects/<int:project_id>/webhook/", WebhookView.as_view()),
]
