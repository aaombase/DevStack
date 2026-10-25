from django.db import transaction
from django.db.models import Count
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from projects.access import get_project_or_404, require_role
from projects.models import Role

from .models import Activity, Task, TaskStatus, log_activity
from .serializers import (
    ActivitySerializer, CommentSerializer, MoveSerializer, TaskSerializer,
)


class TaskFilter(filters.FilterSet):
    # ?sprint=3 for one sprint, ?sprint=none for the backlog.
    sprint = filters.CharFilter(method="filter_sprint")
    assignee = filters.CharFilter(method="filter_assignee")

    class Meta:
        model = Task
        fields = ("project", "status", "type", "priority")

    def filter_sprint(self, queryset, name, value):
        if value == "none":
            return queryset.filter(sprint__isnull=True)
        return queryset.filter(sprint_id=value) if value.isdigit() else queryset.none()

    def filter_assignee(self, queryset, name, value):
        if value == "me":
            return queryset.filter(assignee=self.request.user)
        if value == "none":
            return queryset.filter(assignee__isnull=True)
        return queryset.filter(assignee_id=value) if value.isdigit() else queryset.none()


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    filterset_class = TaskFilter
    search_fields = ("title", "description")
    ordering_fields = ("position", "priority", "created_at", "updated_at", "due_date")

    def get_queryset(self):
        return (
            Task.objects.filter(project__memberships__user=self.request.user)
            .select_related("project", "assignee", "reporter")
            .annotate(comment_count=Count("comments", distinct=True))
        )

    # --- writes: developers+ may edit, maintainers+ may delete -------------

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_role(self.request.user, project, Role.DEVELOPER)
        status_ = serializer.validated_data.get("status", TaskStatus.TODO)
        position = Task.objects.filter(project=project, status=status_).count()
        task = serializer.save(reporter=self.request.user, position=position)
        log_activity(project, self.request.user, "created", task, task.title)

    def perform_update(self, serializer):
        task = serializer.instance
        require_role(self.request.user, task.project, Role.DEVELOPER)
        before = {f: getattr(task, f) for f in ("status", "assignee_id", "sprint_id", "priority")}
        task = serializer.save()
        self._log_changes(task, before)

    def perform_destroy(self, instance):
        require_role(self.request.user, instance.project, Role.MAINTAINER)
        log_activity(instance.project, self.request.user, "deleted", None, instance.key)
        instance.delete()

    def _log_changes(self, task, before):
        user = self.request.user
        if before["status"] != task.status:
            log_activity(
                task.project, user, "moved", task,
                f"{before['status']} -> {task.status}",
            )
        if before["assignee_id"] != task.assignee_id:
            who = task.assignee.username if task.assignee else "nobody"
            log_activity(task.project, user, "assigned", task, f"to {who}")
        if before["sprint_id"] != task.sprint_id:
            log_activity(task.project, user, "rescheduled", task, task.sprint.name if task.sprint else "backlog")
        if before["priority"] != task.priority:
            log_activity(task.project, user, "reprioritised", task, task.get_priority_display())

    # --- kanban ----------------------------------------------------------

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        """Drag-and-drop endpoint: change column and/or position in a column."""
        task = self.get_object()
        require_role(request.user, task.project, Role.DEVELOPER)
        data = MoveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        new_status = data.validated_data["status"]
        old_status = task.status

        with transaction.atomic():
            column = list(
                Task.objects.filter(project=task.project, status=new_status)
                .exclude(pk=task.pk)
                .order_by("position", "id")
            )
            index = min(data.validated_data.get("position", len(column)), len(column))
            task.status = new_status
            task.save()  # also maintains completed_at
            column.insert(index, task)
            for i, t in enumerate(column):
                if t.position != i:
                    Task.objects.filter(pk=t.pk).update(position=i)
            task.position = index

        if old_status != new_status:
            log_activity(task.project, request.user, "moved", task, f"{old_status} -> {new_status}")
        return Response(self.get_serializer(self.get_object()).data)

    # --- comments --------------------------------------------------------

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(CommentSerializer(task.comments.select_related("author"), many=True).data)
        require_role(request.user, task.project, Role.DEVELOPER)
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task, author=request.user)
        log_activity(task.project, request.user, "commented", task, serializer.validated_data["body"][:100])
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ActivityViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ActivitySerializer
    filter_backends = ()

    def get_queryset(self):
        project_id = self.request.query_params.get("project")
        if not project_id:
            raise ValidationError({"project": "This query parameter is required."})
        project = get_project_or_404(self.request.user, project_id)
        return Activity.objects.filter(project=project).select_related("actor", "task", "task__project")[:50]
