
import dataclasses
import fnmatch
import re
import typing as t
from pathlib import Path

import requests
from nr.util.git import Git

from shut.plugins.remote_plugin import VcsRemote, RemotePlugin


@dataclasses.dataclass
class GithubRemote(VcsRemote):

  repo: str

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

  def validate_pull_request_url(self, url: str) -> bool:
    return fnmatch.fnmatch(url, f'{self._get_repo_url()}/pulls/*')

  def get_pull_request_url_from_id(self, pr_id: str) -> str:
    return f'{self._get_repo_url()}/pulls/{pr_id}'

  def validate_issue_url(self, url: str) -> bool:
    return fnmatch.fnmatch(url, f'{self._get_repo_url()}/issues/*')

  def get_issue_url_from_id(self, issue_id: str) -> str:
    return f'{self._get_repo_url()}/issue/{issue_id}'

  def get_username_from_email(self, email: str) -> str:
    response = requests.get(
      f'{self._get_api_url()}/search/users',
      params={'q': email}
    )
    response.raise_for_status()
    results = response.json()
    if not results['items']:
      raise ValueError(f'no GitHub username found for email {email!r}')
    return results['items'][0]['login']

  def get_user_profile_url(self, username: str) -> str:
    return f'{self._get_base_url()}/{username}'

  def get_main_branch(self) -> str:
    owner, repo = self._get_repo()
    response = requests.get(f'{self._get_api_url()}/{owner}/{repo}')
    response.raise_for_status()
    result = response.json()
    return result['default_branch']

  def get_recommended_author(self) -> str | None:
    email = Git().get_config('user.email')
    if email:
      return self.get_username_from_email(email)
    return None


@dataclasses.dataclass
class GithubRemotePlugin(RemotePlugin):

  def detect(self, directory: Path) -> t.Optional['RemotePlugin']:
    # TODO (@NiklasRosenstein): Catch the right exception if its not a Git directory
    remotes = Git(directory).remotes()
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
    return GithubRemote(url)
