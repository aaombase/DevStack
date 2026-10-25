from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.testutils import DevTrackTestCase
from projects.models import Membership, Project, Role, Sprint, SprintStatus
from tasks.models import Task, TaskStatus

User = get_user_model()


class AuthTests(DevTrackTestCase):
    def test_register_then_login_with_jwt(self):
        client = APIClient()
        r = client.post("/api/auth/register/", {
            "username": "newbie", "email": "n@example.com", "password": "correct-horse-9",
        })
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("password", r.data)
        token = client.post("/api/auth/token/", {"username": "newbie", "password": "correct-horse-9"})
        self.assertEqual(token.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        self.assertEqual(client.get("/api/auth/me/").data["username"], "newbie")

    def test_register_rejects_weak_password(self):
        r = APIClient().post("/api/auth/register/", {"username": "x1", "password": "123"})
        self.assertEqual(r.status_code, 400)

    def test_api_requires_authentication(self):
        self.assertEqual(APIClient().get("/api/projects/").status_code, 401)


class ProjectAccessTests(DevTrackTestCase):
    def test_creator_becomes_owner_and_key_is_uppercased(self):
        r = self.as_user(self.outsider).post("/api/projects/", {"name": "Mine", "key": "mine"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["key"], "MINE")
        self.assertEqual(r.data["my_role"], "owner")

    def test_duplicate_key_is_rejected_case_insensitively(self):
        r = self.as_user(self.outsider).post("/api/projects/", {"name": "Dup", "key": "demo"})
        self.assertEqual(r.status_code, 400)

    def test_list_only_shows_my_projects(self):
        self.assertEqual(len(self.as_user(self.outsider).get("/api/projects/").data), 0)
        self.assertEqual(len(self.as_user(self.dev).get("/api/projects/").data), 1)

    def test_non_member_gets_404(self):
        r = self.as_user(self.outsider).get(f"/api/projects/{self.project.id}/")
        self.assertEqual(r.status_code, 404)

    def test_only_maintainers_edit_and_only_owner_deletes(self):
        url = f"/api/projects/{self.project.id}/"
        self.assertEqual(self.as_user(self.dev).patch(url, {"name": "X"}).status_code, 403)
        self.assertEqual(self.as_user(self.owner).patch(url, {"name": "X"}).status_code, 200)
        Membership.objects.filter(user=self.dev).update(role=Role.MAINTAINER)
        self.assertEqual(self.as_user(self.dev).delete(url).status_code, 403)
        self.assertEqual(self.as_user(self.owner).delete(url).status_code, 204)

    def test_webhook_secret_hidden_from_developers(self):
        self.project.github_repo = "acme/demo"
        self.project.save()
        url = f"/api/projects/{self.project.id}/"
        self.assertIsNone(self.as_user(self.dev).get(url).data["github_webhook_secret"])
        self.assertTrue(self.as_user(self.owner).get(url).data["github_webhook_secret"])

    def test_invalid_github_repo_rejected(self):
        r = self.as_user(self.owner).patch(
            f"/api/projects/{self.project.id}/", {"github_repo": "not a repo"}
        )
        self.assertEqual(r.status_code, 400)


class MemberTests(DevTrackTestCase):
    def test_maintainer_adds_member_and_cannot_grant_owner(self):
        url = f"/api/projects/{self.project.id}/members/"
        c = self.as_user(self.owner)
        self.assertEqual(c.post(url, {"username": "mallory", "role": "developer"}).status_code, 201)
        self.assertEqual(c.post(url, {"username": "mallory", "role": "developer"}).status_code, 400)
        self.assertEqual(c.post(url, {"username": "nobody", "role": "viewer"}).status_code, 400)
        r = c.patch(f"{url}{self.outsider.id}/", {"role": "owner"})
        self.assertEqual(r.status_code, 400)

    def test_developer_cannot_add_members(self):
        r = self.as_user(self.dev).post(
            f"/api/projects/{self.project.id}/members/", {"username": "mallory"}
        )
        self.assertEqual(r.status_code, 403)

    def test_owner_cannot_be_removed_and_member_can_leave(self):
        base = f"/api/projects/{self.project.id}/members"
        self.assertEqual(self.as_user(self.owner).delete(f"{base}/{self.owner.id}/").status_code, 403)
        self.assertEqual(self.as_user(self.dev).delete(f"{base}/{self.dev.id}/").status_code, 204)

    def test_removed_member_is_unassigned(self):
        t = Task.objects.create(project=self.project, title="t", assignee=self.dev)
        self.as_user(self.owner).delete(f"/api/projects/{self.project.id}/members/{self.dev.id}/")
        t.refresh_from_db()
        self.assertIsNone(t.assignee)


class SprintTests(DevTrackTestCase):
    def setUp(self):
        super().setUp()
        today = date.today()
        self.sprint = Sprint.objects.create(
            project=self.project, name="S1", start_date=today, end_date=today + timedelta(days=13)
        )
        self.done = Task.objects.create(
            project=self.project, sprint=self.sprint, title="a", story_points=5, status=TaskStatus.DONE
        )
        self.open = Task.objects.create(
            project=self.project, sprint=self.sprint, title="b", story_points=3
        )
        self.url = f"/api/sprints/{self.sprint.id}"

    def test_end_before_start_rejected(self):
        r = self.as_user(self.owner).post("/api/sprints/", {
            "project": self.project.id, "name": "bad",
            "start_date": "2026-02-10", "end_date": "2026-02-01",
        })
        self.assertEqual(r.status_code, 400)

    def test_developer_cannot_create_sprint(self):
        r = self.as_user(self.dev).post("/api/sprints/", {
            "project": self.project.id, "name": "n",
            "start_date": "2026-02-01", "end_date": "2026-02-10",
        })
        self.assertEqual(r.status_code, 403)

    def test_start_snapshots_commitment_and_blocks_second_active(self):
        c = self.as_user(self.owner)
        r = c.post(f"{self.url}/start/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["committed_points"], 8)
        other = Sprint.objects.create(
            project=self.project, name="S2", start_date=date.today(), end_date=date.today()
        )
        self.assertEqual(c.post(f"/api/sprints/{other.id}/start/").status_code, 400)

    def test_complete_moves_unfinished_to_backlog(self):
        c = self.as_user(self.owner)
        c.post(f"{self.url}/start/")
        r = c.post(f"{self.url}/complete/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["completed_points"], 5)
        self.open.refresh_from_db()
        self.assertIsNone(self.open.sprint)
        self.done.refresh_from_db()
        self.assertEqual(self.done.sprint, self.sprint)

    def test_complete_moves_unfinished_to_next_sprint(self):
        nxt = Sprint.objects.create(
            project=self.project, name="S2", start_date=date.today(), end_date=date.today()
        )
        c = self.as_user(self.owner)
        c.post(f"{self.url}/start/")
        r = c.post(f"{self.url}/complete/", {"move_unfinished_to": nxt.id}, format="json")
        self.assertEqual(r.status_code, 200)
        self.open.refresh_from_db()
        self.assertEqual(self.open.sprint, nxt)

    def test_cannot_complete_a_planned_sprint(self):
        self.assertEqual(self.as_user(self.owner).post(f"{self.url}/complete/").status_code, 400)
        self.assertEqual(self.sprint.status, SprintStatus.PLANNED)
