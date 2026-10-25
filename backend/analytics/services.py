"""Metrics computed from tasks, sprints and commits. Pure functions of the DB."""
from collections import Counter
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from integrations.models import Commit
from projects.models import Sprint, SprintStatus
from tasks.models import Task, TaskStatus, TaskType


def _points(qs):
    return qs.aggregate(p=Sum("story_points"))["p"] or 0


def overview(project):
    tasks = project.tasks.all()
    total = tasks.count()
    done = tasks.filter(status=TaskStatus.DONE).count()
    today = timezone.localdate()
    return {
        "total_tasks": total,
        "done_tasks": done,
        "completion_pct": round(100 * done / total) if total else 0,
        "open_bugs": tasks.filter(type=TaskType.BUG).exclude(status=TaskStatus.DONE).count(),
        "overdue": tasks.filter(due_date__lt=today).exclude(status=TaskStatus.DONE).count(),
        "unassigned": tasks.filter(assignee__isnull=True).exclude(status=TaskStatus.DONE).count(),
        "by_status": {
            row["status"]: row["n"] for row in tasks.values("status").annotate(n=Count("id"))
        },
        "by_type": {row["type"]: row["n"] for row in tasks.values("type").annotate(n=Count("id"))},
        "by_priority": {
            row["priority"]: row["n"] for row in tasks.values("priority").annotate(n=Count("id"))
        },
    }


def activity_timeline(project, days=30):
    """Per-day counts of tasks created, tasks completed and commits."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    created = Counter(
        t.date() for t in project.tasks.filter(created_at__date__gte=start).values_list("created_at", flat=True)
    )
    completed = Counter(
        t.date() for t in project.tasks.filter(completed_at__date__gte=start).values_list("completed_at", flat=True)
    )
    commits = Counter(
        t.date() for t in Commit.objects.filter(project=project, committed_at__date__gte=start).values_list("committed_at", flat=True)
    )
    series = []
    for i in range(days):
        day = start + timedelta(days=i)
        series.append(
            {
                "date": day.isoformat(),
                "created": created.get(day, 0),
                "completed": completed.get(day, 0),
                "commits": commits.get(day, 0),
            }
        )
    return series


def contributors(project):
    rows = []
    for m in project.memberships.select_related("user"):
        assigned = project.tasks.filter(assignee=m.user)
        done = assigned.filter(status=TaskStatus.DONE)
        rows.append(
            {
                "user": m.user.username,
                "role": m.role,
                "open_tasks": assigned.exclude(status=TaskStatus.DONE).count(),
                "completed_tasks": done.count(),
                "completed_points": _points(done),
                "commits": Commit.objects.filter(project=project, author_login=m.user.username).count(),
            }
        )
    rows.sort(key=lambda r: (-r["completed_points"], r["user"]))
    return rows


def velocity(project, limit=8):
    """Committed vs completed points for the most recent completed sprints."""
    sprints = list(
        project.sprints.filter(status=SprintStatus.COMPLETED).order_by("-end_date", "-id")[:limit]
    )
    sprints.reverse()
    return [
        {
            "sprint": s.name,
            "committed": s.committed_points or 0,
            "completed": s.completed_points or 0,
        }
        for s in sprints
    ]


def burndown(sprint):
    """Remaining story points per day against an ideal straight line."""
    tasks = list(sprint.tasks.all())
    if sprint.status == SprintStatus.COMPLETED and sprint.committed_points is not None:
        total = sprint.committed_points
    else:
        total = sum(t.story_points for t in tasks)
    today = timezone.localdate()
    last_day = min(sprint.end_date, today) if sprint.status != SprintStatus.COMPLETED else sprint.end_date
    span = max((sprint.end_date - sprint.start_date).days, 1)
    points = []
    day = sprint.start_date
    while day <= max(last_day, sprint.start_date):
        done_pts = sum(
            t.story_points for t in tasks
            if t.completed_at and t.completed_at.date() <= day
        )
        elapsed = (day - sprint.start_date).days
        points.append(
            {
                "date": day.isoformat(),
                "remaining": max(total - done_pts, 0),
                "ideal": round(max(total * (1 - elapsed / span), 0), 1),
            }
        )
        day += timedelta(days=1)
    return {"total_points": total, "points": points}


def project_analytics(project):
    return {
        "overview": overview(project),
        "timeline": activity_timeline(project),
        "contributors": contributors(project),
        "velocity": velocity(project),
    }
