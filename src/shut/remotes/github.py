
import dataclasses
import fnmatch

import requests

from shut.plugins.remote_plugin import RemotePlugin


@dataclasses.dataclass
class GithubRemotePlugin(RemotePlugin):

  repo: str

  def _get_base_url(self) -> str:
    parts = self.repo.split('/')
    if len(parts) == 3:
      return f'https://{parts[0]}/'
    else:
      return f'https://github.com/'

  def _get_repo_url(self) -> str:
    owner, repo = self._get_repo()
    return f'{self._get_base_url()}/{owner}/{repo}'

  def _get_api_url(self) -> str:
    # TODO (@NiklasRosenstein): Can we rely on GHE having a api. subdomain?
    return self._get_base_url().replace('https://', 'https://api.')

  def _get_repo(self) -> tuple[str, str]:
    parts = self.repo.split('/')
    return parts[-2], parts[-1]

  def validate_pull_request_url(self, url: str) -> bool:
    return fnmatch.fnmatch(url, f'{self._get_base_url()}/pulls/*')

  def get_pull_request_url_from_id(self, pr_id: str) -> str:
    return f'{self._get_base_url()}/pulls/{pr_id}'

  def validate_issue_url(self, url: str) -> bool:
    return fnmatch.fnmatch(url, f'{self._get_base_url()}/issues/*')

  def get_issue_url_from_id(self, issue_id: str) -> str:
    return f'{self._get_base_url()}/issue/{issue_id}'

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
