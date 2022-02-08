
import dataclasses
import re

import requests
from nr.util.git import Git

from shut.application import Application, ApplicationPlugin
from shut.changelog.changelog_manager import ChangelogValidator
from shut.commands.log.config import RemoteDetector, RemoteProvider


def is_url(s: str) -> bool:
  return s.startswith('http://') or s.startswith('https://')


def github_get_username_from_email(api_base_url: str, email: str) -> str:
  response = requests.get(f'{api_base_url}/search/users', params={'q': email})
  response.raise_for_status()
  results = response.json()
  if not results['items']:
    raise ValueError(f'no GitHub username found for email {email!r}')
  return results['items'][0]['login']


@dataclasses.dataclass
class GithubChangelogValidator(ChangelogValidator):

  #: The owner and repository name separated by a slash. If the repository is hosted on GitHub enterprise, the
  #: domain of the GHE instance must precede the owner and repository name by another slash (e.g. `ghe.io/owner/repo`).
  repo: str

  def __post_init__(self) -> None:
    self._author_cache: dict[str, str | None] = {}

  def _get_base_url(self) -> str:
    parts = self.repo.split('/')
    if len(parts) == 3:
      return f'https://{parts[0]}'
    else:
      return f'https://github.com'

  def _get_api_url(self) -> str:
    # TODO (@NiklasRosenstein): Can we rely on GHE having a api. subdomain?
    return self._get_base_url().replace('https://', 'https://api.').rstrip('/')

  def _get_repo_url(self) -> str:
    owner, repo = self._get_repo()
    return f'{self._get_base_url()}/{owner}/{repo}'

  def _get_repo(self) -> tuple[str, str]:
    parts = self.repo.split('/')
    return parts[-2], parts[-1]

  def normalize_issue_reference(self, issue: str) -> str:
    issue = issue.lstrip('#')
    if issue.isnumeric():
      return f'{self._get_repo_url()}/issues/{issue}'
    elif is_url(issue):
      return issue
    raise ValueError(f'invalid issue: {issue}')

  def normalize_pr_reference(self, pr: str) -> str:
    pr = pr.lstrip('#')
    if pr.isnumeric():
      return f'{self._get_repo_url()}/pulls/{pr}'
    elif is_url(pr):
      return pr
    raise ValueError(f'invalid pr: {pr}')

  def normalize_author(self, author: str) -> str:
    # If it is an email address, try to see if we can resolve it to a GitHub username.
    # TODO (@NiklasRosenstein): Detect emails in a syntax such as "Full Name <email@address.org>" which is very common.
    if '@' in author and not author.startswith('@'):
      if author in self._author_cache:
        return self._author_cache[author] or author
      try:
        resolved = '@' + github_get_username_from_email(self._get_api_url(), author)
      except ValueError:
        self._author_cache[author] = None
        return author  # Return the email address unchanged.
      self._author_cache[author] = resolved
      return resolved
    return author


class GithubRemoteDetector(RemoteDetector):

  def detect_changelog_validator(self, app: Application) -> ChangelogValidator | None:
    # TODO (@NiklasRosenstein): Catch the right exception if its not a Git directory
    remotes = Git(app.project_directory).remotes()
    for remote in remotes:
      if remote.name == 'origin' and 'github' in remote.fetch:
        break
    else:
      return None

    match = re.search(r'github.com[:/]([^/]+/[^/]+)?', remote.fetch)
    if not match:
      return None

    url = match.group(1)
    if url.endswith('.git'):
      url = url[:-4]

    return GithubChangelogValidator(url)


@dataclasses.dataclass
class GithubRemoteProvider(RemoteProvider):
  repo: str

  def get_changelog_validator(self, app: Application) -> ChangelogValidator:
    return GithubChangelogValidator(self.repo)


@dataclasses.dataclass
class GithubApplicationPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    app.plugins.register(RemoteDetector, 'github', GithubRemoteDetector())
