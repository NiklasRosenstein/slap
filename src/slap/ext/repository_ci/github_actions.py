import logging
import os
import re
import subprocess as sp
from dataclasses import dataclass
from pathlib import Path

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
        self._base_ref: tuple[str, str] | None = None
        self._head_ref: tuple[str, str] | None = None
        self._pull_request: GhPullRequest | None = None
        logger.debug("Pull request ID: %s", self._pull_request_id)

        if self._pull_request_id is not None:
            self._pull_request = get_github_pull_request(
                self._github_api_url, self._repository, self._pull_request_id, self._github_token
            )
            self._base_ref = ("origin", os.environ["GITHUB_BASE_REF"])
            self._head_ref = ("origin", f"pull/{self._pull_request_id}/head")
            # self._head_ref = (self.HEAD_REMOTE_NAME, os.environ["GITHUB_HEAD_REF"])

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

            # # Make sure that there is a remote for the fork.
            # try:
            #     head_remote = self._repo.remote(self.HEAD_REMOTE_NAME)
            # except ValueError:
            #     logger.info(
            #         "Creating %s remote (url: %s)",
            #         self.HEAD_REMOTE_NAME,
            #         self._pull_request.head_html_url,
            #     )
            #     head_remote = self._repo.create_remote(self.HEAD_REMOTE_NAME, self._pull_request.head_html_url)
            # else:
            #     logger.info(
            #         "Updating %s remote (url: %s)",
            #         self.HEAD_REMOTE_NAME,
            #         self._pull_request.head_html_url,
            #     )
            #     head_remote.set_url(self._pull_request.head_html_url)

            # logger.info("Fetching head ref '%s/%s'", *self._head_ref)
            # head_remote.fetch(self._head_ref[1])

            checkout_head = self._head_ref
            self._head_ref = (
                self._head_ref[0],
                self.HEAD_BRANCH_PREFIX + self._pull_request_id + "-" + self._head_ref[1],
            )

            logger.info("Checking out '%s/%s' as '%s'.", *checkout_head, self._head_ref[1])
            self._repo.git.checkout("/".join(checkout_head), "-b", self._head_ref[1])

            assert self._repo.active_branch.name == self._head_ref[1]
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

        logger.info("Showing diff before pushing changes to remote.")
        sp.run(["git", "diff"], check=True)

        user_name = os.environ.get("GIT_USER_NAME", "GitHub Action")
        user_email = os.environ.get("GIT_USER_EMAIL", "github-action@users.noreply.github.com")

        # Use gitpython to add files and commit.
        logger.info("Committing changes to %s/%s", *self._head_ref)
        logger.info("Changed files: %s", ", ".join(str(f) for f in changed_files))
        self._repo.index.add([str(f) for f in changed_files])
        self._repo.index.commit(message=commit_message, author=Actor(user_name, user_email))

        logger.info("Pushing changes to %s/%s", *self._head_ref)
        self._repo.git.push(self._head_ref[0], self._head_ref[1])
