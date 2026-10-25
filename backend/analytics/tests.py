from datetime import timedelta

from django.utils import timezone

from accounts.testutils import DevTrackTestCase
from analytics import services
from integrations.models import Commit
from projects.models import Sprint, SprintStatus
from tasks.models import Task, TaskStatus, TaskType


class AnalyticsTests(DevTrackTestCase):
    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        self.sprint = Sprint.objects.create(
            project=self.project, name="S1", goal="Ship it", status=SprintStatus.ACTIVE,
            start_date=today - timedelta(days=4), end_date=today + timedelta(days=5),
        )
        mk = lambda **kw: Task.objects.create(project=self.project, sprint=self.sprint, **kw)
        self.a = mk(title="a", story_points=5, status=TaskStatus.DONE, assignee=self.dev)
        self.b = mk(title="b", story_points=3, type=TaskType.BUG, assignee=self.dev)
        self.c = mk(title="c", story_points=2, priority=4, due_date=today - timedelta(days=1))
        Task.objects.filter(pk=self.a.pk).update(completed_at=timezone.now() - timedelta(days=2))
        Commit.objects.create(
            project=self.project, sha="a" * 40, message="x", author_login="dev",
            committed_at=timezone.now() - timedelta(days=1),
        )

    def test_overview_numbers(self):
        ov = services.overview(self.project)
        self.assertEqual(ov["total_tasks"], 3)
        self.assertEqual(ov["completion_pct"], 33)
        self.assertEqual(ov["open_bugs"], 1)
        self.assertEqual(ov["overdue"], 1)
        self.assertEqual(ov["unassigned"], 1)
        self.assertEqual(ov["by_status"]["done"], 1)

    def test_timeline_covers_30_days_with_counts(self):
        series = services.activity_timeline(self.project)
        self.assertEqual(len(series), 30)
        self.assertEqual(sum(d["completed"] for d in series), 1)
        self.assertEqual(sum(d["commits"] for d in series), 1)
        self.assertEqual(sum(d["created"] for d in series), 3)

    def test_burndown_drops_when_work_completes(self):
        chart = services.burndown(self.sprint)
        self.assertEqual(chart["total_points"], 10)
        pts = chart["points"]
        self.assertEqual(pts[0]["remaining"], 10)
        self.assertEqual(pts[-1]["remaining"], 5)
        self.assertGreater(pts[0]["ideal"], pts[-1]["ideal"])

    def test_contributors_ranked_by_points(self):
        rows = services.contributors(self.project)
        self.assertEqual(rows[0]["user"], "dev")
        self.assertEqual((rows[0]["completed_points"], rows[0]["open_tasks"], rows[0]["commits"]), (5, 1, 1))

    def test_velocity_uses_snapshots(self):
        Sprint.objects.create(
            project=self.project, name="old", status=SprintStatus.COMPLETED,
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=timezone.localdate() - timedelta(days=16),
            committed_points=20, completed_points=15,
        )
        self.assertEqual(services.velocity(self.project), [{"sprint": "old", "committed": 20, "completed": 15}])

    def test_analytics_endpoint_access(self):
        url = f"/api/projects/{self.project.id}/analytics/"
        r = self.as_user(self.viewer).get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {"overview", "timeline", "contributors", "velocity"})
        self.assertEqual(self.as_user(self.outsider).get(url).status_code, 404)

    def test_summary_flags_risks(self):
        r = self.as_user(self.dev).get(f"/api/projects/{self.project.id}/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["health"], "red")  # critical item open in sprint
        md = r.data["markdown"]
        self.assertIn("# Demo - weekly summary", md)
        self.assertIn("1 overdue task", md)
        self.assertIn("Current sprint: S1", md)
        self.assertIn("DEMO-1 a", md)

    def test_summary_for_empty_project_is_sane(self):
        Task.objects.all().delete()
        r = self.as_user(self.dev).get(f"/api/projects/{self.project.id}/summary/?days=abc")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["health"], "green")

    def test_sprint_report(self):
        r = self.as_user(self.viewer).get(f"/api/sprints/{self.sprint.id}/report/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["committed_points"], r.data["completed_points"]), (10, 5))
        self.assertEqual(r.data["completion_pct"], 50)
        self.assertEqual(r.data["tasks_not_finished"], 2)
        self.assertIn("Delivered 5 of 10 points (50%)", r.data["markdown"])
        self.assertEqual(self.as_user(self.outsider).get(f"/api/sprints/{self.sprint.id}/report/").status_code, 404)
