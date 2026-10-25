import hashlib
import hmac
import json

from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.access import get_project_or_404, require_role
from projects.models import Project, Role
from tasks.models import log_activity

from .github import GitHubClient, GitHubError
from .models import Commit
from .services import (
    normalize_webhook_commit, store_commit, sync_project, upsert_issue,
)


def get_client():
    return GitHubClient()


class SyncView(APIView):
    """Maintainers trigger a pull of issues + commits from the linked repo."""

    throttle_scope = "github_sync"

    def post(self, request, project_id):
        project = get_project_or_404(request.user, project_id)
        require_role(request.user, project, Role.MAINTAINER)
        if not project.github_repo:
            return Response({"detail": "Set the project's GitHub repository first."}, status=400)
        try:
            summary = sync_project(project, get_client())
        except GitHubError as exc:
            return Response({"detail": str(exc)}, status=502)
        log_activity(
            project, request.user, "synced github", None,
            f"{summary['issues_created']} new issues, {summary['commits_added']} new commits",
        )
        return Response(summary)


class CommitListView(APIView):
    def get(self, request, project_id):
        project = get_project_or_404(request.user, project_id)
        commits = Commit.objects.filter(project=project)[:30]
        return Response([
            {
                "sha": c.sha, "message": c.message.splitlines()[0] if c.message else "",
                "author": c.author_login or c.author_name, "committed_at": c.committed_at,
                "url": c.url,
            }
            for c in commits
        ])


class WebhookView(APIView):
    """Receives GitHub webhooks. Authenticated by HMAC signature, not by JWT."""

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def post(self, request, project_id):
        body = request.body
        project = Project.objects.filter(pk=project_id).exclude(github_webhook_secret="").first()
        signature = request.headers.get("X-Hub-Signature-256", "")
        # Same 403 for unknown project and bad signature: don't reveal which.
        if project is None or not self._valid_signature(project.github_webhook_secret, body, signature):
            return HttpResponse("Invalid signature.", status=403)

        try:
            payload = json.loads(body)
        except ValueError:
            return HttpResponse("Invalid JSON.", status=400)
        if str(payload.get("repository", {}).get("full_name", "")).lower() != project.github_repo.lower():
            return HttpResponse("Repository mismatch.", status=400)

        event = request.headers.get("X-GitHub-Event", "")
        if event == "issues" and "issue" in payload:
            upsert_issue(project, payload["issue"])
        elif event == "push":
            for commit in payload.get("commits", []):
                store_commit(project, normalize_webhook_commit(commit))
        return Response({"ok": True})

    @staticmethod
    def _valid_signature(secret, body, header):
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, header)
