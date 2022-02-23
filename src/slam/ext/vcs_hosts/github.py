
import dataclasses
import re

import requests
from nr.util.git import Git

from slam.application import Application
from slam.changelog import is_url
from slam.plugins import VcsHostDetector, VcsHostProvider
from slam.project import Project
from slam.util.vcs import VcsHost


def github_get_username_from_email(api_base_url: str, email: str) -> str:
  response = requests.get(f'{api_base_url}/search/users', params={'q': email})
  response.raise_for_status()
  results = response.json()
  if not results['items']:
    raise ValueError(f'no GitHub username found for email {email!r}')
  return results['items'][0]['login']


@dataclasses.dataclass
class GithubVcsHost(VcsHost):

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
    # TODO (@NiklasRosenstein): Can we rely on GHE having an `api.` subdomain?
    return self._get_base_url().replace('https://', 'https://api.').rstrip('/')

  def _get_repo_url(self) -> str:
    owner, repo = self._get_repo()
    return f'{self._get_base_url()}/{owner}/{repo}'

  def _get_repo(self) -> tuple[str, str]:
    parts = self.repo.split('/')
    return parts[-2], parts[-1]

  def normalize_issue(self, issue: str) -> str | None:
    issue = issue.lstrip('#')
    if issue.isnumeric():
      return f'{self._get_repo_url()}/issues/{issue}'
    elif is_url(issue):
      return issue
    return None

  def normalize_pr(self, pr: str) -> str | None:
    pr = pr.lstrip('#')
    if pr.isnumeric():
      return f'{self._get_repo_url()}/pull/{pr}'
    elif is_url(pr):
      return pr
    return None

  def normalize_author(self, author: str) -> str | None:
    # If it is an email address, try to see if we can resolve it to a GitHub username.
    # TODO (@NiklasRosenstein): Detect emails in a syntax such as "Full Name <email@address.org>" which is very common.
    if '@' in author and not author.startswith('@'):
      if author in self._author_cache:
        return self._author_cache[author]
      try:
        resolved = '@' + github_get_username_from_email(self._get_api_url(), author)
      except ValueError:
        self._author_cache[author] = None
        return author  # Return the email address unchanged.
      self._author_cache[author] = resolved
      return resolved
    return None

  def pr_shortform(self, pr: str) -> str | None:
    return self.issue_shortform(pr)

  def issue_shortform(self, issue: str) -> str | None:
    match = re.search(r'https?://([\w\-\.]+)/(?:|.+/)([\w\-\.\_]+)/([\w\-\.\_]+)/(?:pulls|issues)/(\d+)', issue)
    if match:
      domain, owner, repo, issue_id = match.groups()
      if domain == 'github.com' and self.repo == (owner + '/' + repo):
        return issue_id
      elif self.repo == (domain + '/' + owner + '/' + repo):
        return issue_id
      result = owner + '/' + repo + '#' + issue_id
      if domain != 'github.com':
        result = domain + '/' + result
      return result
    return None


class GithubVcsHostDetector(VcsHostDetector):

  def detect_vcs_host(self, project: Project) -> VcsHost | None:
    # TODO (@NiklasRosenstein): Catch the right exception if its not a Git directory

    git = Git(project.directory)
    if not git.get_toplevel():
      return None

    remotes = git.remotes()
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

    return GithubVcsHost(url)


@dataclasses.dataclass
class GithubVcsHostProvider(VcsHostProvider):
  repo: str

  def get_vcs_host(self, project: Project) -> VcsHost:
    return GithubVcsHost(self.repo)
