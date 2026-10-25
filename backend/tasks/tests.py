from datetime import date

from accounts.testutils import DevTrackTestCase
from projects.models import Membership, Project, Role, Sprint
from tasks.models import Activity, Task, TaskStatus


class TaskCrudTests(DevTrackTestCase):
    def create(self, user, **extra):
        data = {"project": self.project.id, "title": "Fix login", **extra}
        return self.as_user(user).post("/api/tasks/", data, format="json")

    def test_numbers_increment_per_project_and_key_is_readable(self):
        a = self.create(self.dev)
        b = self.create(self.dev)
        self.assertEqual((a.data["key"], b.data["key"]), ("DEMO-1", "DEMO-2"))
        other = Project.objects.create(name="O", key="OTH", owner=self.owner)
        Membership.objects.create(project=other, user=self.owner, role=Role.OWNER)
        r = self.as_user(self.owner).post("/api/tasks/", {"project": other.id, "title": "x"})
        self.assertEqual(r.data["key"], "OTH-1")

    def test_reporter_is_set_and_activity_logged(self):
        r = self.create(self.dev)
        self.assertEqual(r.data["reporter_detail"]["username"], "dev")
        self.assertTrue(Activity.objects.filter(verb="created", task_id=r.data["id"]).exists())

    def test_viewer_can_read_but_not_write(self):
        self.assertEqual(self.create(self.viewer).status_code, 403)
        t = self.create(self.dev).data
        c = self.as_user(self.viewer)
        self.assertEqual(c.get(f"/api/tasks/{t['id']}/").status_code, 200)
        self.assertEqual(c.patch(f"/api/tasks/{t['id']}/", {"title": "hax"}).status_code, 403)
        self.assertEqual(c.post(f"/api/tasks/{t['id']}/move/", {"status": "done"}).status_code, 403)
        self.assertEqual(
            c.post(f"/api/tasks/{t['id']}/comments/", {"body": "hi"}).status_code, 403
        )

    def test_outsider_cannot_see_create_or_touch_tasks(self):
        t = self.create(self.dev).data
        c = self.as_user(self.outsider)
        self.assertEqual(c.get(f"/api/tasks/{t['id']}/").status_code, 404)
        self.assertEqual(c.get("/api/tasks/").data, [])
        self.assertEqual(self.create(self.outsider).status_code, 400)

    def test_only_maintainers_delete(self):
        t = self.create(self.dev).data
        self.assertEqual(self.as_user(self.dev).delete(f"/api/tasks/{t['id']}/").status_code, 403)
        self.assertEqual(self.as_user(self.owner).delete(f"/api/tasks/{t['id']}/").status_code, 204)

    def test_assignee_must_be_member_and_sprint_must_match_project(self):
        self.assertEqual(self.create(self.dev, assignee=self.outsider.id).status_code, 400)
        other = Project.objects.create(name="O", key="OTH", owner=self.owner)
        sprint = Sprint.objects.create(
            project=other, name="x", start_date=date.today(), end_date=date.today()
        )
        self.assertEqual(self.create(self.dev, sprint=sprint.id).status_code, 400)

    def test_task_cannot_change_project(self):
        t = self.create(self.owner).data
        other = Project.objects.create(name="O", key="OTH", owner=self.owner)
        Membership.objects.create(project=other, user=self.owner, role=Role.OWNER)
        r = self.as_user(self.owner).patch(f"/api/tasks/{t['id']}/", {"project": other.id})
        self.assertEqual(r.status_code, 400)

    def test_filters(self):
        sprint = Sprint.objects.create(
            project=self.project, name="s", start_date=date.today(), end_date=date.today()
        )
        self.create(self.dev, type="bug", sprint=sprint.id, assignee=self.dev.id)
        self.create(self.dev, title="backlog item")
        c = self.as_user(self.dev)
        self.assertEqual(len(c.get(f"/api/tasks/?project={self.project.id}&type=bug").data), 1)
        self.assertEqual(len(c.get("/api/tasks/?sprint=none").data), 1)
        self.assertEqual(len(c.get(f"/api/tasks/?sprint={sprint.id}").data), 1)
        self.assertEqual(len(c.get("/api/tasks/?assignee=me").data), 1)
        self.assertEqual(len(c.get("/api/tasks/?search=backlog").data), 1)
        self.assertEqual(len(c.get("/api/tasks/?sprint=abc").data), 0)


class KanbanMoveTests(DevTrackTestCase):
    def setUp(self):
        super().setUp()
        self.t = [
            Task.objects.create(project=self.project, title=f"t{i}", position=i)
            for i in range(3)
        ]

    def move(self, task, status, position=None):
        data = {"status": status} if position is None else {"status": status, "position": position}
        return self.as_user(self.dev).post(f"/api/tasks/{task.id}/move/", data, format="json")

    def test_move_to_done_sets_completed_at_and_back_clears_it(self):
        r = self.move(self.t[0], "done")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data["completed_at"])
        r = self.move(self.t[0], "in_progress")
        self.assertIsNone(r.data["completed_at"])

    def test_reorder_within_column(self):
        self.move(self.t[2], "todo", 0)
        order = list(
            Task.objects.filter(status=TaskStatus.TODO).order_by("position").values_list("title", flat=True)
        )
        self.assertEqual(order, ["t2", "t0", "t1"])

    def test_insert_into_other_column_at_position(self):
        self.move(self.t[0], "review")
        self.move(self.t[1], "review", 0)
        col = list(Task.objects.filter(status="review").order_by("position").values_list("title", flat=True))
        self.assertEqual(col, ["t1", "t0"])
        self.assertEqual(
            list(Task.objects.filter(status="todo").values_list("title", flat=True)), ["t2"]
        )

    def test_position_beyond_end_is_clamped_and_bad_status_rejected(self):
        self.assertEqual(self.move(self.t[0], "done", 99).data["position"], 0)
        self.assertEqual(self.move(self.t[1], "nonsense").status_code, 400)

    def test_move_logs_activity(self):
        self.move(self.t[0], "review")
        self.assertTrue(Activity.objects.filter(verb="moved", task=self.t[0]).exists())


class CommentAndActivityTests(DevTrackTestCase):
    def test_comment_flow(self):
        t = Task.objects.create(project=self.project, title="t")
        c = self.as_user(self.dev)
        r = c.post(f"/api/tasks/{t.id}/comments/", {"body": "looks good"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.get(f"/api/tasks/{t.id}/comments/").data[0]["author"]["username"], "dev")
        self.assertEqual(c.get(f"/api/tasks/{t.id}/").data["comment_count"], 1)

    def test_activity_feed_requires_membership(self):
        url = f"/api/activity/?project={self.project.id}"
        self.assertEqual(self.as_user(self.outsider).get(url).status_code, 404)
        self.assertEqual(self.as_user(self.viewer).get(url).status_code, 200)
        self.assertEqual(self.as_user(self.viewer).get("/api/activity/").status_code, 400)
