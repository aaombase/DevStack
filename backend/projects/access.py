"""Role-based access helpers shared by every app.

Roles, lowest to highest: viewer < developer < maintainer < owner.
  viewer      read everything in the project
  developer   create/edit tasks, comment, move cards
  maintainer  manage sprints, members, GitHub settings, delete tasks
  owner       everything, plus delete the project
"""
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Project, Role


def projects_for(user):
    return Project.objects.filter(memberships__user=user).distinct()


def get_project_or_404(user, project_id):
    """Fetch a project the user belongs to; non-members get a 404, not a 403,
    so project existence isn't leaked."""
    try:
        return projects_for(user).get(pk=project_id)
    except (Project.DoesNotExist, ValueError, TypeError):
        raise NotFound("Project not found.")


def require_role(user, project, minimum=Role.DEVELOPER):
    if not project.has_role(user, minimum):
        raise PermissionDenied(f"This action requires the '{minimum}' role or higher.")
