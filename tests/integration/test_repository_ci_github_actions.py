import json
import os
import re
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from typing import Any, Iterator
from unittest.mock import patch

from git.repo import Repo
from git.util import Actor
from pytest import fixture, mark, raises

from slap.ext.repository_ci.github_actions import (
    GithubActionsRepositoryCIPlugin,
    PullRequestFromForkedRepositoryNotSupported,
    SimpleGithubClient,
)


@dataclass
class MockPullRequestData:
    repository: str
    id: str
    html_url: str
    head_repository: str
    head_html_url: str


class MockGitHubApiServer:
    """
    A simple mock for the GitHub API.
    """

    class Handler(BaseHTTPRequestHandler):
        def __init__(self, *args, pulls: list[MockPullRequestData], **kwargs):
            self._pulls = pulls
            super().__init__(*args, **kwargs)

        def do_GET(self):
            match = re.match(r"/repos/(.+)/pulls/([^/]+)", self.path)
            if match:
                self._handle_pull_request(match.group(1), match.group(2))
                return
            # comments
            match = re.match(r"/repos/(.+)/issues/([^/]+)/comments", self.path)
            if match:
                self._handle_comments_get(match.group(1), match.group(2))
                return

            self.send_error(404)

        def do_POST(self):
            match = re.match(r"/repos/(.+)/issues/([^/]+)/comments", self.path)
            if match:
                self._handle_comment_post(match.group(1), match.group(2))
                return

            self.send_error(404)

        def _handle_pull_request(self, repository: str, pr_id: str) -> None:
            for pull in self._pulls:
                if repository == pull.repository and pr_id == pull.id:
                    break
            else:
                self.send_error(404)
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "html_url": pull.html_url,
                        "head": {
                            "repo": {
                                "full_name": pull.head_repository,
                                "html_url": pull.head_html_url,
                            }
                        },
                    }
                ).encode("utf-8")
            )

        def _handle_comments_get(self, repository: str, pr_id: str) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"[]")

        def _handle_comment_post(self, repository: str, pr_id: str) -> None:
            self.send_response(201)
            self.end_headers()
            self.wfile.write(b'{"id": "foobar", "body": "foobar"}')

    def __init__(self) -> None:
        self._pulls: list[MockPullRequestData] = []
        self._server = HTTPServer(("localhost", 0), self.handler)
        self._thread = Thread(target=self._server.serve_forever)

    def add_pull_request(self, pull: MockPullRequestData) -> None:
        self._pulls.append(pull)

    def handler(self, *args: Any, **kwargs: Any) -> Handler:
        return self.Handler(*args, pulls=self._pulls, **kwargs)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._thread.join()

    @property
    def addr(self) -> str:
        return f"http://localhost:{self._server.server_port}"


@fixture
def mock_api() -> Iterator[MockGitHubApiServer]:
    api = MockGitHubApiServer()
    api.start()
    try:
        yield api
    finally:
        api.stop()


@fixture
def tempdir() -> Iterator[Path]:
    cwd = Path.cwd()
    with TemporaryDirectory() as tempdir:
        os.chdir(tempdir)
        try:
            yield Path(tempdir)
        finally:
            os.chdir(cwd)


def test__SimpleGithubClient__get_pull_request(mock_api: MockGitHubApiServer) -> None:
    mock_api.add_pull_request(
        MockPullRequestData(
            repository="octodad/octo-repo",
            id="123",
            html_url="https://github.com/octodad/octo-repo/pull/123",
            head_repository="octodad/octo-repo",
            head_html_url="https://github.com/octodad/octo-repo/pull/123",
        )
    )

    client = SimpleGithubClient(github_api_url=mock_api.addr, token="")
    response = client.get_pull_request(repository="octodad/octo-repo", pull_request_id="123")
    assert response == SimpleGithubClient.PullRequest(
        html_url="https://github.com/octodad/octo-repo/pull/123",
        head_repository="octodad/octo-repo",
        head_html_url="https://github.com/octodad/octo-repo/pull/123",
    )


@mark.parametrize("event_name", ["pull_request", "pull_request_target"])
def test__GithubActionsRepositoryCIPlugin__forked_pr_push_changes(
    mock_api: MockGitHubApiServer, tempdir: Path, event_name: str
) -> None:
    """
    This integration test checks that the GitHub Actions plugin works correctly when running in GitHub actions
    to deal with a pull request from a forked repository.

    It sets up two local repositories, one for the main repository and one for the forked repository. It also mocks
    the GitHub API and environment variables to simulate a GitHub Actions job running in a pull request from the
    forked repository to the main repository.
    """

    main_repo = tempdir / "main-repo"
    forked_repo = tempdir / "forked-repo"

    # Create the main repository
    main_git = Repo.init(main_repo)
    main_readme = main_repo / "README.md"
    main_readme.write_text("Hello world!\n")
    main_git.index.add(["README.md"])
    main_git.index.commit("Initial commit", author=Actor("Jane Doe", "jane@doe.com"))
    main_git.create_remote("origin", str(main_repo / ".git"))

    # Create the forked repository
    main_git.clone(forked_repo)
    forked_git = Repo(forked_repo)
    forked_readme = forked_repo / "README.md"
    assert forked_readme.exists()
    forked_readme.write_text("Hello world!\nThis line is from forked-repo.\n")
    forked_git.index.add(["README.md"])
    forked_git.index.commit("Initial commit", author=Actor("John Doe", "john@doe.com"))

    # We can't push to a branch that is currently checked out; this is a limitation of not having a real Git server
    # in this test so we have to switch to a different branch.
    forked_git_active_branch = forked_git.active_branch.name
    forked_git.git.checkout("-b", "tmp")

    # Simulate the pull request.
    mock_api.add_pull_request(
        MockPullRequestData(
            repository="main-repo",
            id="123",
            html_url=str(main_repo / ".git"),
            head_repository="forked-repo",
            head_html_url=str(forked_repo / ".git"),
        )
    )
    environ = {
        "GITHUB_API_URL": mock_api.addr,
        "GITHUB_REPOSITORY": "main-repo",
        "GITHUB_HEAD_REF": forked_git_active_branch,
        "GITHUB_BASE_REF": main_git.active_branch.name,
        "GITHUB_TOKEN": "foo",
        "GITHUB_EVENT_NAME": event_name,
    }
    if event_name == "pull_request_target":
        environ["GITHUB_PR_ID"] = "123"
        environ["GITHUB_REF"] = main_git.active_branch.name
    else:
        environ["GITHUB_REF"] = "refs/pull/123/merge"

    with patch.dict("os.environ", environ):
        os.chdir(main_repo)
        plugin = GithubActionsRepositoryCIPlugin()
        plugin.initialize()

        main_head_remote = main_git.remote(GithubActionsRepositoryCIPlugin.HEAD_REMOTE_NAME)
        assert main_head_remote.exists()
        assert main_head_remote.url == str(forked_repo / ".git")

        # After initializing the plugin, the main repository should have the state of the forked repository.
        assert main_readme.read_text() == forked_readme.read_text()

        expect_readme_content = forked_readme.read_text() + "This line is from main-repo automation.\n"
        main_readme.write_text(expect_readme_content)

        # We know that we can't actually support pull requests from forked repositories, so we expect an exception.
        if event_name == "pull_request_target":
            plugin.publish_changes([main_readme], "Update README.md")
        else:
            with raises(PullRequestFromForkedRepositoryNotSupported):
                plugin.publish_changes([main_readme], "Update README.md")

    if event_name == "pull_request_target":
        # Expect that the forked_repo has been updated.
        forked_git.git.checkout(forked_git_active_branch)
        assert forked_readme.read_text() == expect_readme_content
