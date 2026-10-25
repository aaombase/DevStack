from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from projects.models import Membership, Project, Role

User = get_user_model()


class DevTrackTestCase(APITestCase):
    """Creates an owner, a developer, a viewer, an outsider and one project."""

    def setUp(self):
        self.owner = self.make_user("olivia")
        self.dev = self.make_user("dev")
        self.viewer = self.make_user("vera")
        self.outsider = self.make_user("mallory")
        self.project = Project.objects.create(name="Demo", key="DEMO", owner=self.owner)
        Membership.objects.create(project=self.project, user=self.owner, role=Role.OWNER)
        Membership.objects.create(project=self.project, user=self.dev, role=Role.DEVELOPER)
        Membership.objects.create(project=self.project, user=self.viewer, role=Role.VIEWER)

    @staticmethod
    def make_user(name):
        return User.objects.create_user(name, f"{name}@example.com", "pass-12345-x")

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client
