
import functools
import dataclasses
import re
from pathlib import Path

import requests

from slap.changelog import is_url
from slap.repository import Issue, PullRequest, Repository, RepositoryHost


@functools.lru_cache()
def github_get_username_from_email(api_base_url: str, email: str) -> str:
  response = requests.get(f'{api_base_url}/search/users', params={'q': email})
  response.raise_for_status()
  results = response.json()
  if not results['items']:
    raise ValueError(f'no GitHub username found for email {email!r}')
  return results['items'][0]['login']


@dataclasses.dataclass
class GithubRepositoryHost(RepositoryHost):

  #: The owner and repository name separated by a slash. If the repository is hosted on GitHub enterprise, the
  #: domain of the GHE instance must precede the owner and repository name by another slash (e.g. `ghe.io/owner/repo`).
  repo: str

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

  def _get_issue_shortform(self, issue_url: str) -> str:
    match = re.search(r'https?://([\w\-\.]+)/(?:|.+/)([\w\-\.\_]+)/([\w\-\.\_]+)/(?:pulls?|issues)/(\d+)', issue_url)
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
    raise ValueError(f'invalid issue URL: {issue_url!r}')

  def get_username(self, repository: Repository) -> str | None:
    vcs = repository.vcs()
    assert vcs
    email = vcs.get_author().email
    username = github_get_username_from_email(self._get_api_url(), email)
    return ('@' + username) if username else email

  def get_issue_by_reference(self, issue_reference: str) -> Issue:
    issue_reference = issue_reference.lstrip('#')
    if issue_reference.isnumeric():
      id = issue_reference
      url = f'{self._get_repo_url()}/issues/{issue_reference}'
      shortform = '#' + id
    elif is_url(issue_reference):
      url = issue_reference
      shortform = self._get_issue_shortform(issue_reference)
      if shortform.isnumeric():
        id = shortform
        shortform = '#' + id
      else:
        id = shortform
    else:
      raise ValueError(f'bad issue/pull request reference for GitHub: {issue_reference!r}')
    return Issue(id, url, shortform)

  def get_pull_request_by_reference(self, pr_reference: str) -> PullRequest:
    issue = self.get_issue_by_reference(pr_reference)
    return PullRequest(issue.id, issue.url, issue.shortform)

  @staticmethod
  def detect_repository_host(repository: Repository) -> RepositoryHost | None:
    from nr.util.git import Git

    git = Git(repository.directory)
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

    repo = match.group(1)
    if repo.endswith('.git'):
      repo = repo[:-4]

    return GithubRepositoryHost(repo)

  def comment_on_issue(self, issue_reference: str, message: str) -> None:
    raise NotImplementedError

  def create_release(self, version: str, description: str, attachments: list[Path]) -> None:
    raise NotImplementedError
