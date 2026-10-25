from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.serializers import UserSerializer
from projects.access import projects_for

from .models import Activity, Comment, Task, TaskStatus

User = get_user_model()


class TaskSerializer(serializers.ModelSerializer):
    key = serializers.CharField(read_only=True)
    assignee_detail = UserSerializer(source="assignee", read_only=True)
    reporter_detail = UserSerializer(source="reporter", read_only=True)
    comment_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Task
        fields = (
            "id", "key", "number", "project", "sprint", "title", "description",
            "type", "status", "priority", "story_points", "assignee",
            "assignee_detail", "reporter_detail", "due_date", "position",
            "github_issue_number", "github_url", "comment_count",
            "created_at", "updated_at", "completed_at",
        )
        read_only_fields = (
            "id", "key", "number", "position", "github_issue_number", "github_url",
            "created_at", "updated_at", "completed_at",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            # A project the user isn't in looks exactly like one that doesn't exist.
            self.fields["project"].queryset = projects_for(request.user)

    def validate(self, attrs):
        project = attrs.get("project") or (self.instance and self.instance.project)
        if self.instance and "project" in attrs and attrs["project"] != self.instance.project:
            raise serializers.ValidationError({"project": "A task can't move between projects."})
        assignee = attrs.get("assignee")
        if assignee and not project.memberships.filter(user=assignee).exists():
            raise serializers.ValidationError({"assignee": "Assignee must be a project member."})
        sprint = attrs.get("sprint")
        if sprint and sprint.project_id != project.id:
            raise serializers.ValidationError({"sprint": "Sprint belongs to another project."})
        return attrs


class MoveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TaskStatus.choices)
    position = serializers.IntegerField(min_value=0, required=False)


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "author", "body", "created_at")
        read_only_fields = ("id", "author", "created_at")


class ActivitySerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    task_key = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = ("id", "actor", "verb", "detail", "task", "task_key", "created_at")

    def get_task_key(self, obj):
        return obj.task.key if obj.task_id else None
