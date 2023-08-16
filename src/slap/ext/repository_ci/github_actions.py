import logging
import os
import re
import subprocess as sp
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

import requests
from git.repo import Repo
from git.util import Actor

from slap.plugins import RepositoryCIPlugin

logger = logging.getLogger()


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


class SimpleGithubClient:
    @dataclass
    class PullRequest:
        html_url: str
        head_repository: str
        head_html_url: str

    @dataclass
    class Comment:
        id: str
        body: str

    def __init__(self, github_api_url: str, token: str) -> None:
        """
        :param github_api_url: The URL of the GitHub server, e.g. https://api.github.com. In GitHub CI, this is
            available as the environment variable `GITHUB_API_URL`.
        :param token: The token for the GitHub API. In GitHub CI, this is available as the environment variable
            `GITHUB_TOKEN`.
        """

        self._github_api_url = github_api_url
        self._token = token
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": f"Bearer {self._token}",
            }
        )

    def get_pull_request(self, repository: str, pull_request_id: str) -> PullRequest:
        """
        Fetches the metadata of a GitHub pull request.

        :param repository: The repository name, e.g. "slap". In GitHub CI, this is available as the environment variable
            `GITHUB_REPOSITORY`.
        :param pull_request_id: The pull request ID, e.g. "123". In GitHub CI, this is available as the environment
            variable `GITHUB_REF` formatted as `refs/pull/{id}/merge`.

        See https://docs.github.com/en/actions/learn-github-actions/variables for more information.
        """

        response = self._session.get(f"{self._github_api_url}/repos/{repository}/pulls/{pull_request_id}")
        self._raise_for_status(response)
        data = response.json()

        return self.PullRequest(
            html_url=data["html_url"],
            head_repository=data["head"]["repo"]["full_name"],
            head_html_url=data["head"]["repo"]["html_url"],
        )

    def get_pr_comments(self, repository: str, pull_request_id: str) -> list[Comment]:
        """
        Fetches the comments on a GitHub Pull Request.
        """

        response = self._session.get(f"{self._github_api_url}/repos/{repository}/issues/{pull_request_id}/comments")
        self._raise_for_status(response)
        data = response.json()

        return [
            self.Comment(
                id=comment["id"],
                body=comment["body"],
            )
            for comment in data
        ]

    def delete_pr_comment(self, repository: str, comment_id: str) -> None:
        """
        Deletes a comment on a GitHub Pull Request.
        """

        response = self._session.delete(f"{self._github_api_url}/repos/{repository}/issues/comments/{comment_id}")
        self._raise_for_status(response)

    def create_pr_comment(self, repository: str, pull_request_id: str, body: str) -> Comment:
        """
        Creates a comment on a GitHub Pull Request.
        """

        response = self._session.post(
            f"{self._github_api_url}/repos/{repository}/issues/{pull_request_id}/comments",
            json={"body": body},
        )
        self._raise_for_status(response)
        data = response.json()
        return self.Comment(
            id=data["id"],
            body=data["body"],
        )

    def _raise_for_status(self, response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.warning(
                "Requested to '%s' return status code %d with body: %s",
                response.request.url,
                response.status_code,
                response.text,
            )
            raise


class GithubActionsRepositoryCIPlugin(RepositoryCIPlugin):
    """A plugin for use in GitHub Actions via `slap changelog update-pr --use github-actions` which will do all steps
    to push the updated changelogs back to a pull request branch. It should be used only in an action that is run as
    part of a GitHub pull request.

    GitHub environment variables used:

    * `GITHUB_API_URL`
    * `GITHUB_REPOSITORY`
    * `GITHUB_EVENT_NAME`
    * `GITHUB_REF` (the github PR number formatted as `refs/pull/{id}/head`)
    * `GITHUB_PR_ID` -- When running in a `pull_request_target` event, the pull request ID is not available in
        `GITHUB_REF` and must be passed manually to this environment variable from
        `${{ github.event.pull_request.number }}`.

    For pull requests:

    * `GITHUB_HEAD_REF`
    * `GITHUB_BASE_REF`

    Additional environment variables to control the plugin:

    * `GIT_USER_NAME` (defaults to `GitHub Action`)
    * `GIT_USER_EMAIL` (defaults to `github-action@users.noreply.github.com`)
    * `GIT_COMMIT_MESSAGE` (defaults to `Update changelog PR references`)

    Important: This does not currently work properly when the head ref is from a fork instead of the same repository.
    This is because the `GITHUB_TOKEN` does not have the permissions to push back to the forked repository, even if
    you as an individual would be able to. Configuring a GitHub Personl Access Token would also not work because in
    a forked PR, the `pull_request` event does not have access to repository secrets.

    When it is detected that a forked repository is used, the plugin will fail with an error message and post a comment
    to the pull request with a requested to update the changelog. It will then exit with an error to block the GitHub
    job from succeeding.
    """

    HEAD_REMOTE_NAME = "head"
    HEAD_BRANCH_PREFIX = "slap-changelog-update-pr-"
    COMMENT_RE_ID = "slap-changelog-update-pr-comment"

    def create_or_update_comment(self, body: str) -> None:
        assert self._pull_request_id is not None
        prefix = f"<!-- {self.COMMENT_RE_ID} -->"
        body = f"{prefix}\n\n{body}"
        try:
            comments = self._client.get_pr_comments(self._repository, self._pull_request_id)
        except requests.HTTPError:
            logger.exception("Failed to fetch comments on pull request %s", self._pull_request_id)
            comments = []
        for comment in comments:
            if comment.body.strip().startswith(prefix):
                logger.debug("Removing old comment: %s", comment.id)
                self._client.delete_pr_comment(self._repository, comment.id)

        logger.info("Posting comment")
        self._client.create_pr_comment(self._repository, self._pull_request_id, body)

    # RepositoryCIPlugin

    def initialize(self) -> None:
        self._repo = Repo(Path.cwd())
        self._github_api_url = os.environ["GITHUB_API_URL"]
        self._github_token = os.environ.get("GITHUB_TOKEN", "")
        self._client = SimpleGithubClient(self._github_api_url, self._github_token)
        self._repository = os.environ["GITHUB_REPOSITORY"]
        self._ref = os.environ["GITHUB_REF"]
        self._event_name = os.environ["GITHUB_EVENT_NAME"]

        # This information is only available when we're in a pull request workflow..
        self._base_ref: tuple[str, str] | None = None
        self._base_branch: str | None = None
        self._head_ref: tuple[str, str] | None = None
        self._head_branch: str | None = None
        self._pull_request: SimpleGithubClient.PullRequest | None = None
        self._pull_request_id: str | None = None
        self._supports_forked_prs: bool = False

        if self._event_name == "pull_request":
            # The GITHUB_TOKEN won't have the permission to push back to a fork.
            self._pull_request_id = parse_pull_request_id(self._ref)
            self._supports_forked_prs = False
        elif self._event_name == "pull_request_target":
            # The GITHUB_TOKEN does have permission to fork back to a fork, but the pull request ID is not available
            # in GITHUB_REF.
            if "GITHUB_PR_ID" not in os.environ:
                raise RuntimeError(
                    "GITHUB_PR_ID environment variable must be set manually when running in a `pull_request_target` "
                    "event. You can obtain the pull request ID from `${{ github.event.pull_request.number }}`."
                )
            self._pull_request_id = os.environ["GITHUB_PR_ID"]
            self._supports_forked_prs = True
        logger.debug("Pull request ID: %s", self._pull_request_id)

        if self._pull_request_id is not None:
            # We need a GitHub token when running in a pull request. This is so that we can query the GitHub API
            # for the pull request information. Technically, we wouldn't need it for public repositories, but that's
            # a special case we don't handle at the moment.
            if not self._github_token:
                raise RuntimeError(
                    "GITHUB_TOKEN environment variable must be set when running in a pull request workflow."
                )

            self._pull_request = self._client.get_pull_request(self._repository, self._pull_request_id)
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
        assert self._pull_request is not None

        # Make sure checks for this commit are ignored.
        # See https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks#skipping-and-requesting-checks-for-individual-commits  # noqa: E501
        commit_message = f"{commit_message}\n\nskip-checks: true"

        def _diff() -> str:
            return sp.check_output(["git", "diff"]).decode("utf-8")

        if not self._supports_forked_prs and self._pull_request.head_repository != self._repository:
            message = (
                "This pull request is from a forked repository (`%s`). The `GITHUB_TOKEN` available in CI does not "
                "have the permissions to push back to the branch from the forked repository. Please manually apply "
                "and push the following changes:\n\n```diff\n%s\n```\n"
            )
            message_args = (self._pull_request.head_repository, _diff())
            logger.error(message, *message_args)
            self.create_or_update_comment(message % message_args)
            raise PullRequestFromForkedRepositoryNotSupported(self._pull_request.head_repository)

        # NOTE(@NiklasRosenstein): A lot of what follows is based on the assumption that the head repository
        #       may be a fork and that we can push to it; so once that actually becomes true, we should be able
        #       to get rid of the check above and be finally happy.

        print(_diff())

        user_name = os.environ.get("GIT_USER_NAME", "GitHub Action")
        user_email = os.environ.get("GIT_USER_EMAIL", "github-action@users.noreply.github.com")

        # If the repository lives under a symlinked directory, Repo.index.add() will complain if an aliased
        # filename is passed instead of the real path. This is an issue for example when running unit tests
        # on OSX where /tmp is a symlink to /private/tmp.
        changed_files = [f.resolve() for f in changed_files]

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
            ).strip()
            askpass = Path(tmpdir) / "askpass.sh"
            askpass.write_text(askpass_script)
            askpass.chmod(0o700)
            # logger.info("Using %s as GIT_ASKPASS, content: %s", askpass, askpass_script)
            environ = self._repo.git.environment().copy()
            self._repo.git.update_environment(GIT_ASKPASS=str(askpass))
            try:
                logger.info("Pushing changes to %s/%s", *self._head_ref)
                self._repo.git.push(self._head_ref[0], self._head_branch + ":" + self._head_ref[1])
            finally:
                self._repo.git.environment().clear()
                self._repo.git.environment().update(environ)


class PullRequestFromForkedRepositoryNotSupported(RuntimeError):
    pass
