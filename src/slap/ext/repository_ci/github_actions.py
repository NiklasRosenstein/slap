import logging
import os
import re
import subprocess as sp
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest.mock import patch

import requests
from git.repo import Repo
from git.util import Actor

from slap.plugins import RepositoryCIPlugin

logger = logging.getLogger()


@dataclass
class GhPullRequest:
    html_url: str
    head_repository: str
    head_html_url: str


def get_github_pull_request(github_api_url: str, repository: str, pull_request_id: str, token: str) -> GhPullRequest:
    """
    Fetches the metadata of a GitHub pull request.

    :param github_api_url: The URL of the GitHub server, e.g. https://api.github.com. In GitHub CI, this is
        available as the environment variable `GITHUB_API_URL`.
    :param repository: The repository name, e.g. "slap". In GitHub CI, this is available as the environment variable
        `GITHUB_REPOSITORY`.
    :param pull_request_id: The pull request ID, e.g. "123". In GitHub CI, this is available as the environment
        variable `GITHUB_REF` formatted as `refs/pull/{id}/merge`.
    :param token: The token for the GitHub API. In GitHub CI, this is available as the environment variable
        `GITHUB_TOKEN`.

    See https://docs.github.com/en/actions/learn-github-actions/variables for more information.
    """

    response = requests.get(
        url=f"{github_api_url}/repos/{repository}/pulls/{pull_request_id}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        },
    )
    response.raise_for_status()
    data = response.json()

    return GhPullRequest(
        html_url=data["html_url"],
        head_repository=data["head"]["repo"]["full_name"],
        head_html_url=data["head"]["repo"]["html_url"],
    )


def parse_pull_request_id(github_ref: str) -> str | None:
    """
    Parses the pull request ID from the environment variable `GITHUB_REF` which is formatted as `refs/pull/{id}`.

    :param github_ref: The value of the environment variable `GITHUB_REF`.
    :return: The pull request ID or None if it could not be parsed.
    """

    match = re.match(r"refs/pull/(\d+)", github_ref)
    if not match:
        return None
    return match.group(1)


class GithubActionsRepositoryCIPlugin(RepositoryCIPlugin):
    """A plugin for use in GitHub Actions via `slap changelog update-pr --use github-actions` which will do all steps
    to push the updated changelogs back to a pull request branch. It should be used only in an action that is run as
    part of a GitHub pull request.

    GitHub environment variables used:

    * `GITHUB_API_URL`
    * `GITHUB_REPOSITORY`
    * `GITHUB_REF` (the github PR number formatted as `refs/pull/{id}`)

    For pull requests:

    * `GITHUB_HEAD_REF`
    * `GITHUB_BASE_REF`

    Additional environment variables to control the plugin:

    * `GIT_USER_NAME` (defaults to `GitHub Action`)
    * `GIT_USER_EMAIL` (defaults to `github-action@users.noreply.github.com`)
    * `GIT_COMMIT_MESSAGE` (defaults to `Update changelog PR references`)
    """

    HEAD_REMOTE_NAME = "head"
    HEAD_BRANCH_PREFIX = "slap-changelog-update-pr-"

    def initialize(self) -> None:
        self._repo = Repo(Path.cwd())
        self._github_api_url = os.environ["GITHUB_API_URL"]
        self._repository = os.environ["GITHUB_REPOSITORY"]
        self._ref = os.environ["GITHUB_REF"]
        self._github_token = os.environ["GITHUB_TOKEN"]
        self._pull_request_id = parse_pull_request_id(self._ref)
        logger.debug("Pull request ID: %s", self._pull_request_id)

        # This information is only available when we're in a pull request workflow..
        self._base_ref: tuple[str, str] | None = None
        self._base_branch: str | None = None
        self._head_ref: tuple[str, str] | None = None
        self._head_branch: str | None = None
        self._pull_request: GhPullRequest | None = None

        if self._pull_request_id is not None:
            self._pull_request = get_github_pull_request(
                self._github_api_url,
                self._repository,
                self._pull_request_id,
                self._github_token,
            )
            self._base_ref = ("origin", os.environ["GITHUB_BASE_REF"])
            self._base_branch = self.HEAD_BRANCH_PREFIX + self._pull_request_id + "-base"

            # NOTE(@NiklasRosenstein): We can't use the pull/<pr>/head ref because it is a hidden Git ref
            #       that Github won't allow pushing to. We actually need to push to the head repository
            #       directly.
            # self._head_ref = ("origin", f"pull/{self._pull_request_id}/head")
            self._head_ref = (self.HEAD_REMOTE_NAME, os.environ["GITHUB_HEAD_REF"])
            self._head_branch = self.HEAD_BRANCH_PREFIX + self._pull_request_id + "-head"

            logger.info(
                "This is a GitHub pull request (id: %s) %s/%s → %s/%s",
                self._pull_request_id,
                self._pull_request.head_repository,
                self._head_ref[1],
                self._repository,
                self._base_ref[1],
            )

            logger.info("Fetching base ref '%s/%s'", *self._base_ref)
            base_remote = self._repo.remote(self._base_ref[0])
            base_remote.fetch(self._base_ref[1])

            # Make sure that there is a remote for the fork.
            try:
                head_remote = self._repo.remote(self.HEAD_REMOTE_NAME)
            except ValueError:
                logger.info(
                    "Creating %s remote (url: %s)",
                    self.HEAD_REMOTE_NAME,
                    self._pull_request.head_html_url,
                )
                head_remote = self._repo.create_remote(self.HEAD_REMOTE_NAME, self._pull_request.head_html_url)
            else:
                logger.info(
                    "Updating %s remote (url: %s)",
                    self.HEAD_REMOTE_NAME,
                    self._pull_request.head_html_url,
                )
                head_remote.set_url(self._pull_request.head_html_url)

            logger.info("Fetching head ref '%s/%s'", *self._head_ref)
            head_remote = self._repo.remote(self._head_ref[0])
            head_remote.fetch(self._head_ref[1] + ":" + self._head_branch)

            logger.info("Checking out '%s/%s' as '%s'.", *self._head_ref, self._head_branch)
            self._repo.git.checkout(self._head_branch)  # "/".join(self._head_ref[:2]), "-b", self._head_branch)

            assert self._repo.active_branch.name == self._head_branch
        else:
            logger.info("This is not a GitHub pull request.")

    def get_base_ref(self) -> str:
        if self._pull_request_id is None:
            raise RuntimeError("Not in a pull request")
        assert self._base_ref is not None
        return "/".join(self._base_ref)

    def get_pr(self) -> str:
        if self._pull_request_id is None:
            raise RuntimeError("Not in a pull request")
        assert self._pull_request is not None
        return self._pull_request.html_url

    def publish_changes(self, changed_files: list[Path], commit_message: str) -> None:
        if self._pull_request_id is None:
            raise RuntimeError("Not in a pull request")
        assert self._head_ref is not None
        assert self._head_branch is not None

        logger.info("Showing diff before pushing changes to remote.")
        sp.run(["git", "diff"], check=True)

        user_name = os.environ.get("GIT_USER_NAME", "GitHub Action")
        user_email = os.environ.get("GIT_USER_EMAIL", "github-action@users.noreply.github.com")

        # Use gitpython to add files and commit.
        logger.info("Committing changes to %s/%s", *self._head_ref)
        logger.info("Changed files: %s", ", ".join(str(f) for f in changed_files))
        self._repo.index.add([str(f) for f in changed_files])
        self._repo.index.commit(message=commit_message, author=Actor(user_name, user_email))

        with TemporaryDirectory() as tmpdir:
            askpass_script = dedent(
                f"""
                #!/bin/sh
                case "$1" in
                    Username*) echo "github-actions[bot]" ;;
                    Password*) echo "{self._github_token}" ;;
                    *) exit 1 ;;
                esac
                """
            )
            askpass = Path(tmpdir) / "askpass.sh"
            askpass.write_text(askpass_script)
            askpass.chmod(0o700)
            environ = self._repo.git.environment().copy()
            self._repo.git.update_environment(GIT_ASKPASS=str(askpass))
            try:
                logger.info("Pushing changes to %s/%s", *self._head_ref)
                self._repo.git.push(self._head_ref[0], self._head_branch + ":" + self._head_ref[1])
            finally:
                self._repo.git.environment().clear()
                self._repo.git.environment().update(environ)
