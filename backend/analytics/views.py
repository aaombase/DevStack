from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.access import get_project_or_404
from projects.models import Sprint

from . import reports, services


class ProjectAnalyticsView(APIView):
    def get(self, request, project_id):
        project = get_project_or_404(request.user, project_id)
        return Response(services.project_analytics(project))


class ProjectSummaryView(APIView):
    def get(self, request, project_id):
        project = get_project_or_404(request.user, project_id)
        try:
            days = min(max(int(request.query_params.get("days", 7)), 1), 90)
        except ValueError:
            days = 7
        return Response(reports.project_summary(project, days))


class SprintReportView(APIView):
    def get(self, request, sprint_id):
        try:
            sprint = Sprint.objects.select_related("project").get(
                pk=sprint_id, project__memberships__user=request.user
            )
        except Sprint.DoesNotExist:
            raise NotFound("Sprint not found.")
        return Response(reports.sprint_report(sprint))
