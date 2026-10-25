from django.contrib import admin

from .models import Activity, Comment, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "type", "status", "priority", "assignee", "sprint")
    list_filter = ("status", "type", "priority", "project")
    search_fields = ("title",)


admin.site.register(Comment)
admin.site.register(Activity)
