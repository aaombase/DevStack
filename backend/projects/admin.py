from django.contrib import admin

from .models import Membership, Project, Sprint


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "owner", "github_repo", "created_at")
    search_fields = ("key", "name")
    inlines = [MembershipInline]


@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "status", "start_date", "end_date")
    list_filter = ("status",)
