from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.serializers import UserSerializer

from .access import projects_for
from .models import Membership, Project, Role, Sprint

User = get_user_model()

GITHUB_REPO_RE = r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"


class ProjectSerializer(serializers.ModelSerializer):
    my_role = serializers.SerializerMethodField()
    owner = UserSerializer(read_only=True)
    github_repo = serializers.RegexField(
        GITHUB_REPO_RE, required=False, allow_blank=True, max_length=200
    )
    github_webhook_secret = serializers.SerializerMethodField()
    open_tasks = serializers.IntegerField(read_only=True, required=False)
    total_tasks = serializers.IntegerField(read_only=True, required=False)
    done_tasks = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Project
        fields = (
            "id", "name", "key", "description", "owner", "github_repo",
            "github_webhook_secret", "created_at", "my_role",
            "open_tasks", "total_tasks", "done_tasks",
        )
        read_only_fields = ("id", "owner", "created_at")

    def get_my_role(self, obj):
        return obj.role_of(self.context["request"].user)

    def get_github_webhook_secret(self, obj):
        # The secret authenticates webhooks, so only maintainers may see it.
        if obj.has_role(self.context["request"].user, Role.MAINTAINER):
            return obj.github_webhook_secret
        return None

    def validate_key(self, value):
        value = value.upper()
        clash = Project.objects.filter(key__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("A project with this key already exists.")
        if (
            self.instance
            and self.instance.key != value
            and self.instance.tasks.exists()
        ):
            raise serializers.ValidationError(
                "The project key can't change once tasks exist."
            )
        return value


class MemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    username = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Membership
        fields = ("id", "user", "username", "role", "joined_at")
        read_only_fields = ("id", "joined_at")

    def validate_role(self, value):
        if value == Role.OWNER:
            raise serializers.ValidationError("The owner role can't be assigned.")
        return value


class SprintSerializer(serializers.ModelSerializer):
    task_count = serializers.IntegerField(read_only=True, required=False)
    total_points = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Sprint
        fields = (
            "id", "project", "name", "goal", "start_date", "end_date", "status",
            "committed_points", "completed_points", "task_count", "total_points",
            "created_at",
        )
        read_only_fields = (
            "id", "status", "committed_points", "completed_points", "created_at",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            self.fields["project"].queryset = projects_for(request.user)

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError("end_date must be on or after start_date.")
        if self.instance and "project" in attrs and attrs["project"] != self.instance.project:
            raise serializers.ValidationError("A sprint can't move between projects.")
        return attrs
