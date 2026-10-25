"""Populate a realistic demo project: python manage.py seed_demo [--reset]."""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from integrations.models import Commit
from projects.models import Membership, Project, Role, Sprint, SprintStatus
from tasks.models import Task, TaskStatus, TaskType, log_activity

User = get_user_model()

DEMO_PASSWORD = "devtrack-demo-1"

# (title, type, points, priority)
SPRINT_ONE = [
    ("Set up CI pipeline", "task", 3, 2), ("Design database schema", "story", 5, 3),
    ("User registration and login", "story", 5, 3), ("Fix password reset email typo", "bug", 1, 1),
    ("Project CRUD endpoints", "task", 5, 3), ("Role-based permissions", "story", 8, 4),
]
SPRINT_TWO = [
    ("Kanban board drag and drop", "story", 8, 3), ("Task comments", "task", 3, 2),
    ("Fix card jumps after refresh", "bug", 2, 3), ("Sprint start/complete flow", "story", 5, 3),
    ("Activity feed", "task", 3, 2), ("Crash when assignee is removed", "bug", 2, 4),
    ("Burndown chart", "story", 5, 3), ("GitHub issue import", "story", 8, 3),
]
SPRINT_THREE = [
    ("Weekly project summary", "story", 5, 3), ("Webhook signature check", "task", 2, 3),
    ("Dark mode", "task", 3, 1), ("Export sprint report", "task", 3, 2),
]
BACKLOG = [
    ("Slack notifications", "story", 8, 2), ("Time tracking", "story", 13, 1),
    ("Bulk edit tasks", "task", 5, 2), ("Mobile layout polish", "task", 3, 1),
    ("Rate limit login attempts", "bug", 2, 3),
]


class Command(BaseCommand):
    help = "Create demo users, a project, sprints, tasks and commits."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete the demo project first.")

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(7)
        now = timezone.now()
        today = timezone.localdate()

        if options["reset"]:
            Project.objects.filter(key="DEV").delete()
        elif Project.objects.filter(key="DEV").exists():
            self.stdout.write("Demo project already exists (use --reset to rebuild).")
            return

        users = {}
        for name in ("demo", "alice", "bob", "carol"):
            user, created = User.objects.get_or_create(
                username=name, defaults={"email": f"{name}@example.com"}
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            users[name] = user

        project = Project.objects.create(
            name="DevTrack Platform", key="DEV", owner=users["demo"],
            description="The platform that tracks itself.", github_repo="acme/devtrack",
        )
        for name, role in (("demo", Role.OWNER), ("alice", Role.MAINTAINER),
                           ("bob", Role.DEVELOPER), ("carol", Role.VIEWER)):
            Membership.objects.create(project=project, user=users[name], role=role)
        workers = [users["demo"], users["alice"], users["bob"]]

        s1 = Sprint.objects.create(
            project=project, name="Sprint 1 - Foundations", goal="Auth, projects and permissions",
            status=SprintStatus.COMPLETED, start_date=today - timedelta(days=28),
            end_date=today - timedelta(days=15),
        )
        s2 = Sprint.objects.create(
            project=project, name="Sprint 2 - Board & Sprints", goal="A usable Kanban board",
            status=SprintStatus.COMPLETED, start_date=today - timedelta(days=14),
            end_date=today - timedelta(days=1),
        )
        s3 = Sprint.objects.create(
            project=project, name="Sprint 3 - Insights", goal="Analytics and automatic summaries",
            status=SprintStatus.ACTIVE, start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=8),
        )
        s4 = Sprint.objects.create(
            project=project, name="Sprint 4 - Polish", goal="Notifications and UX",
            start_date=today + timedelta(days=9), end_date=today + timedelta(days=22),
        )

        def make(items, sprint, start_offset, finished, partial=0):
            """Create tasks; `finished` of them complete, `partial` more in progress/review."""
            made = []
            for i, (title, kind, points, prio) in enumerate(items):
                done = i < finished
                if done:
                    status = TaskStatus.DONE
                elif i < finished + partial:
                    status = rng.choice([TaskStatus.IN_PROGRESS, TaskStatus.REVIEW])
                else:
                    status = TaskStatus.TODO
                task = Task.objects.create(
                    project=project, sprint=sprint, title=title, type=kind, story_points=points,
                    priority=prio, status=status, assignee=rng.choice(workers),
                    reporter=users["demo"], position=i,
                )
                created = now - timedelta(days=start_offset, hours=rng.randint(0, 6))
                completed = (
                    created + timedelta(days=rng.randint(1, 6), hours=rng.randint(0, 8))
                    if done else None
                )
                Task.objects.filter(pk=task.pk).update(
                    created_at=created, completed_at=min(completed, now) if completed else None
                )
                made.append(task)
            return made

        make(SPRINT_ONE, s1, 28, finished=len(SPRINT_ONE))
        make(SPRINT_TWO, s2, 14, finished=6)  # two items slipped
        for t in s2.tasks.exclude(status=TaskStatus.DONE):
            t.sprint = s3
            t.save()
        s1.committed_points, s1.completed_points = 27, 27
        s2.committed_points = sum(p for _, _, p, _ in SPRINT_TWO)
        s2.completed_points = s2.committed_points - sum(t[2] for t in SPRINT_TWO[6:])
        s1.save()
        s2.save()

        make(SPRINT_THREE, s3, 5, finished=1, partial=2)
        s3.committed_points = sum(t.story_points for t in s3.tasks.all())
        s3.save()
        # Overdue + unassigned items, so the summary has something to flag.
        overdue = s3.tasks.exclude(status=TaskStatus.DONE).first()
        Task.objects.filter(pk=overdue.pk).update(due_date=today - timedelta(days=2))
        Task.objects.filter(pk=s3.tasks.exclude(status=TaskStatus.DONE).last().pk).update(assignee=None)

        make(BACKLOG, None, 3, finished=0)

        for day in range(30):
            for _ in range(rng.choice([0, 0, 1, 2, 3])):
                author = rng.choice(workers)
                Commit.objects.create(
                    project=project, sha=f"{rng.getrandbits(160):040x}",
                    message=rng.choice([
                        "Refactor serializers", "Add tests for permissions", "Fix flaky board test",
                        "Wire up analytics endpoint", "Tidy imports", "Update README",
                    ]),
                    author_login=author.username, author_name=author.username.title(),
                    committed_at=now - timedelta(days=day, hours=rng.randint(0, 10)),
                    url="https://github.com/acme/devtrack/commit/demo",
                )

        log_activity(project, users["demo"], "started sprint", None, s3.name)
        self.stdout.write(self.style.SUCCESS(
            f"Demo ready. Log in as demo / {DEMO_PASSWORD} (also alice, bob, carol)."
        ))
