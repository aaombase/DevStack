import hashlib
import hmac
import json
from unittest import mock

from accounts.testutils import DevTrackTestCase
from integrations.github import GitHubError
from integrations.models import Commit
from tasks.models import Activity, Task, TaskStatus, TaskType

ISSUES = [
    {"number": 1, "title": "Crash on start", "state": "open", "html_url": "https://gh/1",
     "labels": [{"name": "bug"}, {"name": "critical"}], "body": "boom"},
    {"number": 2, "title": "Add dark mode", "state": "closed", "html_url": "https://gh/2",
     "labels": [], "body": None},
]
COMMITS = [
    {"sha": "a" * 40, "html_url": "https://gh/c/a", "author": {"login": "dev"},
     "commit": {"message": "Fix crash, closes DEMO-1\n\nlong body",
                "author": {"name": "Dev", "date": "2026-10-20T10:00:00Z"}}},
]


class FakeClient:
    def issues(self, repo, **kw):
        return ISSUES

    def commits(self, repo, **kw):
        return COMMITS


class SyncTests(DevTrackTestCase):
    def setUp(self):
        super().setUp()
        self.project.github_repo = "acme/demo"
        self.project.save()
        Task.objects.create(project=self.project, title="local")  # DEMO-1, linked by commit
        self.url = f"/api/integrations/projects/{self.project.id}/sync/"

    def sync(self, user=None):
        with mock.patch("integrations.views.get_client", return_value=FakeClient()):
            return self.as_user(user or self.owner).post(self.url)

    def test_sync_imports_issues_and_commits(self):
        r = self.sync()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"issues_created": 2, "issues_updated": 0, "commits_added": 1})
        bug = Task.objects.get(github_issue_number=1)
        self.assertEqual((bug.type, bug.priority, bug.status), (TaskType.BUG, 4, TaskStatus.TODO))
        self.assertEqual(Task.objects.get(github_issue_number=2).status, TaskStatus.DONE)
        self.assertEqual(Commit.objects.count(), 1)

    def test_commit_mentioning_task_key_is_linked(self):
        self.sync()
        self.assertTrue(Activity.objects.filter(verb="linked commit", task__number=1).exists())

    def test_sync_is_idempotent_and_keeps_local_edits(self):
        self.sync()
        Task.objects.filter(github_issue_number=1).update(story_points=8, status=TaskStatus.IN_PROGRESS)
        r = self.sync()
        self.assertEqual(r.data, {"issues_created": 0, "issues_updated": 0, "commits_added": 0})
        bug = Task.objects.get(github_issue_number=1)
        self.assertEqual((bug.story_points, bug.status), (8, TaskStatus.IN_PROGRESS))

    def test_closed_upstream_marks_local_task_done(self):
        self.sync()
        closed = [{**ISSUES[0], "state": "closed"}, ISSUES[1]]
        with mock.patch("integrations.views.get_client") as gc:
            gc.return_value.issues.return_value = closed
            gc.return_value.commits.return_value = []
            r = self.as_user(self.owner).post(self.url)
        self.assertEqual(r.data["issues_updated"], 1)
        self.assertEqual(Task.objects.get(github_issue_number=1).status, TaskStatus.DONE)

    def test_developer_cannot_sync(self):
        self.assertEqual(self.sync(self.dev).status_code, 403)

    def test_requires_repo_and_surfaces_github_errors(self):
        self.project.github_repo = ""
        self.project.save()
        self.assertEqual(self.as_user(self.owner).post(self.url).status_code, 400)
        self.project.github_repo = "acme/demo"
        self.project.save()
        with mock.patch("integrations.views.get_client") as gc:
            gc.return_value.issues.side_effect = GitHubError("Repository not found")
            r = self.as_user(self.owner).post(self.url)
        self.assertEqual((r.status_code, r.data["detail"]), (502, "Repository not found"))


class WebhookTests(DevTrackTestCase):
    def setUp(self):
        super().setUp()
        self.project.github_repo = "acme/demo"
        self.project.save()
        self.url = f"/api/integrations/projects/{self.project.id}/webhook/"

    def post(self, event, payload, secret=None, signature=None):
        body = json.dumps(payload).encode()
        secret = secret or self.project.github_webhook_secret
        sig = signature or "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post(
            self.url, body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig, HTTP_X_GITHUB_EVENT=event,
        )

    def test_issue_event_creates_task(self):
        r = self.post("issues", {"repository": {"full_name": "acme/demo"}, "issue": ISSUES[0]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Task.objects.get(github_issue_number=1).type, TaskType.BUG)

    def test_push_event_stores_commits(self):
        r = self.post("push", {"repository": {"full_name": "acme/demo"}, "commits": [
            {"id": "b" * 40, "message": "work", "timestamp": "2026-10-21T09:00:00+02:00",
             "url": "https://gh/c/b", "author": {"name": "Dev", "username": "dev"}},
        ]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Commit.objects.get().author_login, "dev")

    def test_bad_signature_rejected(self):
        r = self.post("issues", {"repository": {"full_name": "acme/demo"}, "issue": ISSUES[0]},
                      signature="sha256=deadbeef")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Task.objects.count(), 0)

    def test_wrong_secret_and_unknown_project_rejected(self):
        r = self.post("ping", {"repository": {"full_name": "acme/demo"}}, secret="wrong")
        self.assertEqual(r.status_code, 403)
        r = self.client.post("/api/integrations/projects/9999/webhook/", b"{}",
                             content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_payload_for_other_repo_rejected(self):
        r = self.post("issues", {"repository": {"full_name": "evil/other"}, "issue": ISSUES[0]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Task.objects.count(), 0)
