"""Thin GitHub REST client. Only the read endpoints DevTrack needs."""
import requests
from django.conf import settings


class GitHubError(Exception):
    """Raised for any failed call, with a message safe to show to the user."""


class GitHubClient:
    PER_PAGE = 100

    def __init__(self, token=None, session=None, base_url=None):
        self.base_url = (base_url or settings.GITHUB_API_URL).rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        )
        token = token if token is not None else settings.GITHUB_TOKEN
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get_pages(self, path, params=None, max_pages=3):
        params = {"per_page": self.PER_PAGE, **(params or {})}
        items = []
        for page in range(1, max_pages + 1):
            try:
                resp = self.session.get(
                    f"{self.base_url}{path}", params={**params, "page": page}, timeout=15
                )
            except requests.RequestException as exc:
                raise GitHubError(f"Could not reach GitHub: {exc.__class__.__name__}") from exc
            if resp.status_code == 404:
                raise GitHubError("Repository not found (or the token can't see it).")
            if resp.status_code in (401, 403):
                raise GitHubError("GitHub rejected the request (bad token or rate limit hit).")
            if not resp.ok:
                raise GitHubError(f"GitHub returned HTTP {resp.status_code}.")
            batch = resp.json()
            items.extend(batch)
            if len(batch) < self.PER_PAGE:
                break
        return items

    def issues(self, repo, since=None, max_pages=3):
        """Issues only: GitHub's issues endpoint also returns pull requests."""
        params = {"state": "all", "sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since
        items = self._get_pages(f"/repos/{repo}/issues", params, max_pages)
        return [i for i in items if "pull_request" not in i]

    def commits(self, repo, since=None, max_pages=3):
        params = {"since": since} if since else {}
        return self._get_pages(f"/repos/{repo}/commits", params, max_pages)
