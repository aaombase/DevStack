from django.contrib import admin

from .models import Commit


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ("sha", "project", "author_login", "committed_at")
    list_filter = ("project",)
