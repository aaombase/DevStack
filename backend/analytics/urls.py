from django.urls import path

from .views import ProjectAnalyticsView, ProjectSummaryView, SprintReportView

urlpatterns = [
    path("projects/<int:project_id>/analytics/", ProjectAnalyticsView.as_view()),
    path("projects/<int:project_id>/summary/", ProjectSummaryView.as_view()),
    path("sprints/<int:sprint_id>/report/", SprintReportView.as_view()),
]
