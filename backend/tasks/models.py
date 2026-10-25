from django.conf import settings
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone


class TaskStatus(models.TextChoices):
    TODO = "todo", "To Do"
    IN_PROGRESS = "in_progress", "In Progress"
    REVIEW = "review", "In Review"
    DONE = "done", "Done"


class TaskType(models.TextChoices):
    TASK = "task", "Task"
    BUG = "bug", "Bug"
    STORY = "story", "Story"


class Priority(models.IntegerChoices):
    LOW = 1, "Low"
    MEDIUM = 2, "Medium"
    HIGH = 3, "High"
    CRITICAL = 4, "Critical"


class Task(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="tasks"
    )
    sprint = models.ForeignKey(
        "projects.Sprint", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="tasks",
    )
    number = models.PositiveIntegerField(editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=10, choices=TaskType.choices, default=TaskType.TASK)
    status = models.CharField(
        max_length=12, choices=TaskStatus.choices, default=TaskStatus.TODO, db_index=True
    )
    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices, default=Priority.MEDIUM
    )
    story_points = models.PositiveSmallIntegerField(default=0)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_tasks",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="reported_tasks",
    )
    due_date = models.DateField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0, help_text="Order within a Kanban column.")
    github_issue_number = models.PositiveIntegerField(null=True, blank=True)
    github_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=("project", "number"), name="unique_task_number"),
            models.UniqueConstraint(
                fields=("project", "github_issue_number"),
                condition=models.Q(github_issue_number__isnull=False),
                name="unique_github_issue_per_project",
            ),
        ]
        indexes = [models.Index(fields=("project", "status"))]

    def __str__(self):
        return f"{self.key}: {self.title}"

    @property
    def key(self):
        return f"{self.project.key}-{self.number}"

    def save(self, *args, **kwargs):
        # Keep completed_at in step with status so analytics can trust it.
        if self.status == TaskStatus.DONE:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None

        if self._state.adding and not self.number:
            with transaction.atomic():
                last = Task.objects.filter(project=self.project).aggregate(m=Max("number"))["m"]
                self.number = (last or 0) + 1
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="comments"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class Activity(models.Model):
    """Append-only audit trail shown in the project's activity feed."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="activity"
    )
    task = models.ForeignKey(
        Task, null=True, blank=True, on_delete=models.SET_NULL, related_name="activity"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    verb = models.CharField(max_length=40)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name_plural = "activity"


def log_activity(project, actor, verb, task=None, detail=""):
    return Activity.objects.create(
        project=project, actor=actor, verb=verb, task=task, detail=detail[:300]
    )
