"""Human-readable summaries generated from the numbers in services.py.

No AI involved: these are deterministic templates, so the output is cheap,
instant and always consistent with the data on screen.
"""
from datetime import timedelta

from django.utils import timezone

from projects.models import SprintStatus
from tasks.models import Priority, TaskStatus, TaskType

from . import services


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _health(overview, sprint_info):
    """Traffic-light status plus the reasons behind it."""
    reasons = []
    level = "green"
    if overview["overdue"]:
        reasons.append(f"{_plural(overview['overdue'], 'task')} overdue")
        level = "amber"
    if sprint_info and sprint_info["behind_by_points"] > 0:
        reasons.append(f"sprint is {sprint_info['behind_by_points']} points behind the ideal burndown")
        level = "amber"
    if sprint_info and sprint_info["critical_open"]:
        reasons.append(f"{_plural(sprint_info['critical_open'], 'critical item')} still open in the sprint")
        level = "red"
    if overview["open_bugs"] >= 10:
        reasons.append(f"{overview['open_bugs']} open bugs")
        level = "red"
    return level, reasons


def _active_sprint_info(project):
    sprint = project.sprints.filter(status=SprintStatus.ACTIVE).first()
    if not sprint:
        return None
    chart = services.burndown(sprint)
    latest = chart["points"][-1] if chart["points"] else {"remaining": 0, "ideal": 0}
    open_tasks = sprint.tasks.exclude(status=TaskStatus.DONE)
    today = timezone.localdate()
    return {
        "sprint": sprint,
        "total_points": chart["total_points"],
        "remaining_points": latest["remaining"],
        "behind_by_points": max(round(latest["remaining"] - latest["ideal"]), 0),
        "days_left": max((sprint.end_date - today).days, 0),
        "critical_open": open_tasks.filter(priority=Priority.CRITICAL).count(),
    }


def project_summary(project, days=7):
    ov = services.overview(project)
    since = timezone.now() - timedelta(days=days)
    done_recent = list(project.tasks.filter(completed_at__gte=since).order_by("-completed_at"))
    created_recent = project.tasks.filter(created_at__gte=since).count()
    commits_recent = project.commits.filter(committed_at__gte=since).count()
    sprint_info = _active_sprint_info(project)
    level, reasons = _health(ov, sprint_info)

    lines = [f"# {project.name} - weekly summary", ""]
    lines.append(
        f"**Overall:** {ov['completion_pct']}% complete "
        f"({ov['done_tasks']} of {_plural(ov['total_tasks'], 'task')} done)."
    )
    lines.append(f"**Health:** {level.upper()}" + (f" - {'; '.join(reasons)}." if reasons else " - on track."))
    lines += ["", f"## Last {days} days"]
    lines.append(
        f"- {_plural(len(done_recent), 'task')} completed, {created_recent} created, "
        f"{_plural(commits_recent, 'commit')} pushed."
    )
    for t in done_recent[:5]:
        lines.append(f"  - {t.key} {t.title}")
    if len(done_recent) > 5:
        lines.append(f"  - ...and {len(done_recent) - 5} more")

    if sprint_info:
        s = sprint_info["sprint"]
        lines += ["", f"## Current sprint: {s.name}"]
        if s.goal:
            lines.append(f"Goal: {s.goal}")
        lines.append(
            f"- {sprint_info['remaining_points']} of {sprint_info['total_points']} points remaining, "
            f"{_plural(sprint_info['days_left'], 'day')} left."
        )

    attention = []
    if ov["overdue"]:
        attention.append(f"{_plural(ov['overdue'], 'overdue task')}")
    if ov["open_bugs"]:
        attention.append(f"{_plural(ov['open_bugs'], 'open bug')}")
    if ov["unassigned"]:
        attention.append(f"{ov['unassigned']} unassigned")
    if attention:
        lines += ["", "## Needs attention", "- " + ", ".join(attention)]

    return {
        "health": level,
        "health_reasons": reasons,
        "period_days": days,
        "completed_recently": len(done_recent),
        "markdown": "\n".join(lines),
    }


def sprint_report(sprint):
    tasks = list(sprint.tasks.select_related("assignee"))
    done = [t for t in tasks if t.status == TaskStatus.DONE]
    carried = [t for t in tasks if t.status != TaskStatus.DONE]
    chart = services.burndown(sprint)

    if sprint.status == SprintStatus.COMPLETED and sprint.committed_points is not None:
        committed, completed = sprint.committed_points, sprint.completed_points or 0
    else:
        committed = sum(t.story_points for t in tasks)
        completed = sum(t.story_points for t in done)
    pct = round(100 * completed / committed) if committed else 0

    by_person = {}
    for t in done:
        name = t.assignee.username if t.assignee else "unassigned"
        row = by_person.setdefault(name, {"user": name, "tasks": 0, "points": 0})
        row["tasks"] += 1
        row["points"] += t.story_points
    people = sorted(by_person.values(), key=lambda r: (-r["points"], r["user"]))

    bugs_fixed = sum(1 for t in done if t.type == TaskType.BUG)

    lines = [f"# Sprint report: {sprint.name}", ""]
    lines.append(f"{sprint.start_date} to {sprint.end_date} ({sprint.get_status_display()})")
    if sprint.goal:
        lines.append(f"**Goal:** {sprint.goal}")
    lines += [
        "",
        f"**Delivered {completed} of {committed} points ({pct}%)** - "
        f"{_plural(len(done), 'task')} done, {len(carried)} not finished.",
        f"Bugs fixed: {bugs_fixed}.",
    ]
    if done:
        lines += ["", "## Completed"] + [f"- {t.key} {t.title} ({t.story_points} pts)" for t in done]
    if carried:
        lines += ["", "## Not finished"] + [f"- {t.key} {t.title} [{t.get_status_display()}]" for t in carried]
    if people:
        lines += ["", "## By person"] + [f"- {p['user']}: {p['tasks']} tasks, {p['points']} pts" for p in people]

    return {
        "sprint": sprint.id,
        "name": sprint.name,
        "status": sprint.status,
        "committed_points": committed,
        "completed_points": completed,
        "completion_pct": pct,
        "tasks_done": len(done),
        "tasks_not_finished": len(carried),
        "bugs_fixed": bugs_fixed,
        "by_person": people,
        "burndown": chart,
        "markdown": "\n".join(lines),
    }
