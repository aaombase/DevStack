from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from tasks.models import Task, TaskStatus, log_activity

from .access import projects_for, require_role
from .models import Membership, Project, Role, Sprint, SprintStatus
from .serializers import MemberSerializer, ProjectSerializer, SprintSerializer

User = get_user_model()


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    filterset_fields = ()
    search_fields = ("name", "key")

    def get_queryset(self):
        return projects_for(self.request.user).select_related("owner").annotate(
            total_tasks=Count("tasks", distinct=True),
            done_tasks=Count("tasks", filter=Q(tasks__status=TaskStatus.DONE), distinct=True),
            open_tasks=Count("tasks", filter=~Q(tasks__status=TaskStatus.DONE), distinct=True),
        )

    @transaction.atomic
    def perform_create(self, serializer):
        project = serializer.save(owner=self.request.user)
        Membership.objects.create(project=project, user=self.request.user, role=Role.OWNER)
        log_activity(project, self.request.user, "created project", None, project.name)

    def perform_update(self, serializer):
        require_role(self.request.user, serializer.instance, Role.MAINTAINER)
        serializer.save()

    def perform_destroy(self, instance):
        require_role(self.request.user, instance, Role.OWNER)
        instance.delete()

    # --- members ---------------------------------------------------------

    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        project = self.get_object()
        if request.method == "GET":
            qs = project.memberships.select_related("user").order_by("user__username")
            return Response(MemberSerializer(qs, many=True).data)

        require_role(request.user, project, Role.MAINTAINER)
        serializer = MemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data.get("username")
        if not username:
            raise ValidationError({"username": "This field is required."})
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValidationError({"username": "No such user."})
        if project.memberships.filter(user=user).exists():
            raise ValidationError({"username": "Already a member of this project."})
        member = Membership.objects.create(
            project=project, user=user, role=serializer.validated_data.get("role", Role.DEVELOPER)
        )
        log_activity(project, request.user, "added member", None, f"{user.username} as {member.role}")
        return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"members/(?P<user_id>\d+)")
    def member_detail(self, request, pk=None, user_id=None):
        project = self.get_object()
        try:
            member = project.memberships.select_related("user").get(user_id=user_id)
        except Membership.DoesNotExist:
            raise ValidationError({"detail": "Not a member of this project."})
        if member.role == Role.OWNER:
            raise PermissionDenied("The project owner can't be changed or removed.")

        if request.method == "DELETE":
            # Members may leave on their own; removing others needs a maintainer.
            if member.user_id != request.user.id:
                require_role(request.user, project, Role.MAINTAINER)
            project.tasks.filter(assignee=member.user).update(assignee=None)
            log_activity(project, request.user, "removed member", None, member.user.username)
            member.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        require_role(request.user, project, Role.MAINTAINER)
        serializer = MemberSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(project, request.user, "changed role", None, f"{member.user.username} -> {member.role}")
        return Response(serializer.data)


class SprintViewSet(viewsets.ModelViewSet):
    serializer_class = SprintSerializer
    filterset_fields = ("project", "status")

    def get_queryset(self):
        return Sprint.objects.filter(project__memberships__user=self.request.user).annotate(
            task_count=Count("tasks", distinct=True),
            total_points=Sum("tasks__story_points"),
        )

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_role(self.request.user, project, Role.MAINTAINER)
        sprint = serializer.save()
        log_activity(project, self.request.user, "planned sprint", None, sprint.name)

    def perform_update(self, serializer):
        require_role(self.request.user, serializer.instance.project, Role.MAINTAINER)
        serializer.save()

    def perform_destroy(self, instance):
        require_role(self.request.user, instance.project, Role.MAINTAINER)
        instance.delete()  # tasks fall back to the backlog (SET_NULL)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        sprint = self.get_object()
        require_role(request.user, sprint.project, Role.MAINTAINER)
        if sprint.status != SprintStatus.PLANNED:
            raise ValidationError("Only planned sprints can be started.")
        if sprint.project.sprints.filter(status=SprintStatus.ACTIVE).exists():
            raise ValidationError("This project already has an active sprint.")
        sprint.status = SprintStatus.ACTIVE
        sprint.committed_points = sprint.tasks.aggregate(p=Sum("story_points"))["p"] or 0
        sprint.save()
        log_activity(sprint.project, request.user, "started sprint", None, sprint.name)
        return Response(SprintSerializer(sprint).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def complete(self, request, pk=None):
        """Close the sprint; unfinished tasks go to the backlog or a named sprint."""
        sprint = self.get_object()
        require_role(request.user, sprint.project, Role.MAINTAINER)
        if sprint.status != SprintStatus.ACTIVE:
            raise ValidationError("Only active sprints can be completed.")

        target = None
        dest = request.data.get("move_unfinished_to", "backlog")
        if dest != "backlog":
            try:
                target = sprint.project.sprints.exclude(pk=sprint.pk).exclude(
                    status=SprintStatus.COMPLETED
                ).get(pk=dest)
            except (Sprint.DoesNotExist, ValueError, TypeError):
                raise ValidationError({"move_unfinished_to": "Use 'backlog' or an open sprint in this project."})

        sprint.completed_points = (
            sprint.tasks.filter(status=TaskStatus.DONE).aggregate(p=Sum("story_points"))["p"] or 0
        )
        sprint.tasks.exclude(status=TaskStatus.DONE).update(sprint=target)
        sprint.status = SprintStatus.COMPLETED
        sprint.save()
        log_activity(
            sprint.project, request.user, "completed sprint", None,
            f"{sprint.name}: {sprint.completed_points}/{sprint.committed_points} pts",
        )
        return Response(SprintSerializer(sprint).data)
