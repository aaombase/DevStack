"""Turn GitHub payloads (REST API or webhook) into DevTrack tasks and commits."""
import re

from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_datetime

from tasks.models import Priority, Task, TaskStatus, TaskType, log_activity

from .models import Commit


def _task_status_for(state):
    return TaskStatus.DONE if state == "closed" else TaskStatus.TODO


def _priority_from_labels(labels):
    joined = " ".join(labels)
    if "critical" in joined or "urgent" in joined:
        return Priority.CRITICAL
    if "high" in joined:
        return Priority.HIGH
    if "low" in joined:
        return Priority.LOW
    return Priority.MEDIUM


def upsert_issue(project, issue):
    """Create or update the task mirroring a GitHub issue.

    Returns "created", "updated" or "unchanged". For existing tasks only the
    open/closed state and the title are synced, so local edits (assignee,
    sprint, points, Kanban column) are never overwritten.
    """
    number = issue["number"]
    labels = [(label.get("name") or "").lower() for label in issue.get("labels", [])]
    wants_done = issue.get("state") == "closed"
    task = project.tasks.filter(github_issue_number=number).first()

    if task is None:
        position = project.tasks.filter(status=_task_status_for(issue.get("state"))).count()
        try:
            with transaction.atomic():
                Task.objects.create(
                    project=project,
                    github_issue_number=number,
                    github_url=issue.get("html_url", ""),
                    title=(issue.get("title") or f"GitHub issue #{number}")[:200],
                    description=issue.get("body") or "",
                    type=TaskType.BUG if "bug" in labels else TaskType.TASK,
                    priority=_priority_from_labels(labels),
                    status=_task_status_for(issue.get("state")),
                    position=position,
                )
        except IntegrityError:  # a concurrent sync created it first
            return "unchanged"
        return "created"

    changed = False
    title = (issue.get("title") or task.title)[:200]
    if title != task.title:
        task.title, changed = title, True
    is_done = task.status == TaskStatus.DONE
    if wants_done and not is_done:
        task.status, changed = TaskStatus.DONE, True
    elif not wants_done and is_done:
        task.status, changed = TaskStatus.TODO, True
    if changed:
        task.save()
    return "updated" if changed else "unchanged"


def normalize_api_commit(item):
    """Shape returned by GET /repos/{repo}/commits."""
    commit = item.get("commit", {})
    author = commit.get("author") or {}
    return {
        "sha": item["sha"],
        "message": commit.get("message", ""),
        "author_name": author.get("name", ""),
        "author_login": (item.get("author") or {}).get("login", ""),
        "committed_at": author.get("date"),
        "url": item.get("html_url", ""),
    }


def normalize_webhook_commit(item):
    """Shape of each entry in a `push` webhook's `commits` array."""
    author = item.get("author") or {}
    return {
        "sha": item["id"],
        "message": item.get("message", ""),
        "author_name": author.get("name", ""),
        "author_login": author.get("username", ""),
        "committed_at": item.get("timestamp"),
        "url": item.get("url", ""),
    }


def store_commit(project, data):
    """Save a normalized commit once; link it to tasks it mentions (KEY-12).

    Returns True when the commit was new.
    """
    committed_at = parse_datetime(data["committed_at"] or "")
    if committed_at is None:
        return False
    commit, created = Commit.objects.get_or_create(
        project=project,
        sha=data["sha"],
        defaults={
            "message": data["message"],
            "author_name": data["author_name"][:200],
            "author_login": data["author_login"][:100],
            "committed_at": committed_at,
            "url": data["url"],
        },
    )
    if created:
        pattern = re.compile(rf"\b{re.escape(project.key)}-(\d+)\b", re.IGNORECASE)
        headline = data["message"].splitlines()[0][:120] if data["message"] else ""
        for number in sorted({int(n) for n in pattern.findall(data["message"])}):
            task = project.tasks.filter(number=number).first()
            if task:
                log_activity(project, None, "linked commit", task, f"{data['sha'][:7]} {headline}")
    return created


def sync_project(project, client):
    """Pull issues and commits for the project's repo. Returns a summary dict."""
    repo = project.github_repo
    summary = {"issues_created": 0, "issues_updated": 0, "commits_added": 0}
    for issue in client.issues(repo):
        result = upsert_issue(project, issue)
        if result == "created":
            summary["issues_created"] += 1
        elif result == "updated":
            summary["issues_updated"] += 1
    for item in client.commits(repo):
        if store_commit(project, normalize_api_commit(item)):
            summary["commits_added"] += 1
    return summary
