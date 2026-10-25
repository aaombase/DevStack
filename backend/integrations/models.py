from django.db import models


class Commit(models.Model):
    """A GitHub commit mirrored locally so analytics don't depend on the API."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="commits"
    )
    sha = models.CharField(max_length=40)
    message = models.TextField(blank=True)
    author_name = models.CharField(max_length=200, blank=True)
    author_login = models.CharField(max_length=100, blank=True)
    committed_at = models.DateTimeField(db_index=True)
    url = models.URLField(blank=True)

    class Meta:
        ordering = ("-committed_at",)
        constraints = [
            models.UniqueConstraint(fields=("project", "sha"), name="unique_commit_per_project")
        ]

    def __str__(self):
        return f"{self.sha[:7]} {self.message.splitlines()[0][:60] if self.message else ''}"
