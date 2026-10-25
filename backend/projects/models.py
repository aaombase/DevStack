import secrets

from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    MAINTAINER = "maintainer", "Maintainer"
    DEVELOPER = "developer", "Developer"
    VIEWER = "viewer", "Viewer"


# Higher number = more privileges. Used for "at least this role" checks.
ROLE_RANK = {Role.VIEWER: 0, Role.DEVELOPER: 1, Role.MAINTAINER: 2, Role.OWNER: 3}


class Project(models.Model):
    name = models.CharField(max_length=120)
    key = models.SlugField(
        max_length=10,
        unique=True,
        help_text="Short prefix for task IDs, e.g. DEV -> DEV-12.",
    )
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_projects"
    )
    github_repo = models.CharField(
        max_length=200, blank=True, help_text="owner/name, e.g. django/django"
    )
    github_webhook_secret = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.key} - {self.name}"

    def save(self, *args, **kwargs):
        self.key = self.key.upper()
        if self.github_repo and not self.github_webhook_secret:
            self.github_webhook_secret = secrets.token_hex(20)
        super().save(*args, **kwargs)

    def role_of(self, user):
        if not user or not user.is_authenticated:
            return None
        return (
            self.memberships.filter(user=user).values_list("role", flat=True).first()
        )

    def has_role(self, user, minimum):
        role = self.role_of(user)
        return role is not None and ROLE_RANK[role] >= ROLE_RANK[minimum]


class Membership(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.DEVELOPER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("project", "user"), name="unique_project_member"
            )
        ]

    def __str__(self):
        return f"{self.user} @ {self.project.key} ({self.role})"


class SprintStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"


class Sprint(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="sprints"
    )
    name = models.CharField(max_length=120)
    goal = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=10, choices=SprintStatus.choices, default=SprintStatus.PLANNED
    )
    # Snapshots taken when the sprint starts / completes, so velocity stays
    # accurate after unfinished work is moved out of the sprint.
    committed_points = models.PositiveIntegerField(null=True, blank=True)
    completed_points = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-start_date", "-id")

    def __str__(self):
        return f"{self.project.key} / {self.name}"
