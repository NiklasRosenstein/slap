
import abc
import dataclasses
import enum
import re
import typing as t
from pathlib import Path

import requests
from nr.util.functional import Consumer
from nr.util.git import Git as _Git, NoCurrentBranchError
from nr.util.generic import T

from slam.changelog import is_url


class FileStatus(enum.Enum):
  NONE = enum.auto()
  ADDED = enum.auto()
  MODIFIED = enum.auto()
  RENAMED = enum.auto()
  DELETED = enum.auto()
  UNKNOWN = enum.auto()


@dataclasses.dataclass
class FileInfo:
  path: Path
  staging: FileStatus
  disk: FileStatus


@dataclasses.dataclass
class Remote:
  name: str
  url: str
  default: bool


@dataclasses.dataclass
class Author:
  name: str | None
  email: str | None


class Vcs(abc.ABC):
  """ Interface to perform actions on a local version control system and its remote counterpart. """

  @abc.abstractmethod
  def get_toplevel(self) -> Path: ...

  @abc.abstractmethod
  def get_web_url(self) -> str | None:
    """ Try to identify the web URL of the repository. """

  @abc.abstractmethod
  def get_remotes(self) -> t.Sequence[Remote]:
    """ Return a sequence of the known remote copies that the local version can be synced with. At least one of the
    returned remotes should be marked as the default remote via #Remote.default. """

  @abc.abstractmethod
  def get_current_branch(self) -> str | None:
    """ Return the name of the current branch in the local repository. This is used by Slam to ensure that the user
    is on the right branch before creating a new release. """

  @abc.abstractmethod
  def get_author(self) -> Author:
    """ Determine the author details from the repository or VCS settings. """

  @abc.abstractmethod
  def get_all_files(self) -> t.Sequence[Path]:
    """ Return a sequence of all the files known to the VCS. """

  @abc.abstractmethod
  def get_changed_files(self) -> t.Sequence[FileInfo]:
    """ Return the status of all files in the version control repository that have been changed or are unknown to the
    VCS (and not ignored). """

  @abc.abstractmethod
  def get_file_contents(self, file: Path, revision: str) -> bytes | None:
    """ Return the contents of the file in a given revision. Return `None` if the file does not exist. """

  @abc.abstractmethod
  def commit_files(
    self,
    files: t.Sequence[Path],
    commit_message: str,
    *,
    tag_name: str | None = None,
    push: Remote | None = None,
    force: bool = False,
    allow_empty: bool = False,
    email: str | None = None,
    name: str | None = None,
    log_line: Consumer[str] | None = None,
  ) -> None:
    """ Commit the given files into the VCS, and optionally create a tag with the given name. If a remote is specified
    for the *push* argument, the commit that was just created on the current branch as well as the tag name if one was
    specified will be pushed to the remote. """

  @classmethod
  @abc.abstractclassmethod
  def detect(cls: type[T], path: Path) -> T | None: ...


class VcsHost(abc.ABC):
  """ Interface for performing actions on a VCS repository host provider and its particular instance. """

  def normalize_pr(self, pr: str) -> str | None:
    """ Normalize the PR reference, which may be in a short form or full form (e.g. PR ID vs URL) and return.
    Return None if the PR is not in a normalized form and cannot be normalized. """

    return None

  def normalize_issue(self, issue: str) -> str | None:
    """ Sames as #normalize_pr() but for issues. """

  def normalize_author(self, author: str) -> str | None:
    """ Normalize an author name, for example converting an email address to a username, or None if the author
    does not adhere to a normal form and cannot be normalized. """

    return None

  def pr_shortform(self, pr: str) -> str | None:
    """ Return the shortform of a normalized PR reference, or None if there is no shortform. """

    return None

  def issue_shortform(self, issue: str) -> str | None:
    """ Return the shortform of a normalized issue reference, or None if there is no shortform. """

    return None

  @staticmethod
  def null() -> 'VcsHost':
    return VcsHost()


class Git(Vcs):

  def __init__(self, directory: Path) -> None:
    self._git = _Git(directory)
    assert self._git.get_toplevel() is not None, f'Not a Git repository: {directory}'

  def __repr__(self) -> str:
    return f'Git("{self._git.path}")'

  def get_toplevel(self) -> Path:
    toplevel = self._git.get_toplevel()
    assert toplevel is not None
    return Path(toplevel)

  def get_web_url(self) -> str | None:
    remote = next((r for r in self._git.remotes() if r.name == 'origin'), None)
    if not remote:
      return None
    url = remote.fetch
    if url.endswith('.git'):
      url = url[:-4]
    if url.startswith('http'):
      return url
    match = re.match(r'\w+@(.*)$', url)
    if match:
      return 'https://' + match.group(1)
    return None

  def get_remotes(self) -> t.Sequence[Remote]:
    result = []
    for remote in self._git.remotes():
      default = remote.name == 'origin'
      result.append(Remote(remote.name, remote.push, default))
    return result

  def get_current_branch(self) -> str | None:
    try:
      return self._git.get_current_branch_name()
    except NoCurrentBranchError:
      return None

  def get_author(self) -> Author:
    name = self._git.get_config('user.name')
    email = self._git.get_config('user.email')
    return Author(name, email)

  def get_all_files(self) -> t.Sequence[Path]:
    return [self._git.path / f for f in self._git.get_files()]

  def get_changed_files(self) -> t.Sequence[FileInfo]:
    result = []
    for file in self._git.get_status():
      result.append(FileInfo(
        Path(file.filename),
        self._git_file_status(file.mode[0]),
        self._git_file_status(file.mode[1])
      ))
    return result

  def get_file_contents(self, file: Path, revision: str) -> bytes | None:
    try:
      return self._git.get_file_contents(str(file), revision)
    except FileNotFoundError:
      return None

  def commit_files(
    self,
    files: t.Sequence[Path],
    commit_message: str,
    *,
    tag_name: str | None = None,
    push: Remote | None = None,
    force: bool = False,
    allow_empty: bool = False,
    email: str | None = None,
    name: str | None = None,
    log_line: Consumer[str] | None = None,
  ) -> None:
    # TODO (@NiklasRosenstein): Capture stdout from Git subprocess and redirect to log_line().
    self._git.add([str(f.resolve()) for f in files])

    commit_command = ['git']
    if email:
      commit_command += ['-c', f'user.email={email}']
    if name:
      commit_command += ['-c', f'user.name={name}']
    commit_command += ['commit', '-m', commit_message]
    if allow_empty:
      commit_command += ['--allow-empty']
    self._git.check_call(commit_command)

    if tag_name is not None:
      self._git.tag(tag_name, force)
    if push is not None:
      refs = [self._git.get_current_branch_name()]
      if tag_name is not None:
        refs.append(tag_name)
      self._git.push(push.name, *refs, force=force)

  @classmethod
  def detect(cls, path: Path) -> t.Union['Git', None]:
    if _Git(path).get_toplevel() is not None:
      return Git(path)
    return None

  @staticmethod
  def _git_file_status(mode: str) -> FileStatus:
    return {
      ' ': FileStatus.NONE,
      'A': FileStatus.ADDED,
      'M': FileStatus.MODIFIED,
      'R': FileStatus.RENAMED,
      'D': FileStatus.DELETED,
      '?': FileStatus.UNKNOWN,
    }[mode]


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
        resolved = '@' + GithubVcsHost.github_get_username_from_email(self._get_api_url(), author)
      except ValueError:
        self._author_cache[author] = None
        return author  # Return the email address unchanged.
      self._author_cache[author] = resolved
      return resolved
    return None

  def pr_shortform(self, pr: str) -> str | None:
    return self.issue_shortform(pr)

  def issue_shortform(self, issue: str) -> str | None:
    match = re.search(r'https?://([\w\-\.]+)/(?:|.+/)([\w\-\.\_]+)/([\w\-\.\_]+)/(?:pulls?|issues)/(\d+)', issue)
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

  @staticmethod
  def detect(path: Path) -> VcsHost | None:
    git = _Git(path)
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

  @staticmethod
  def github_get_username_from_email(api_base_url: str, email: str) -> str:
    response = requests.get(f'{api_base_url}/search/users', params={'q': email})
    response.raise_for_status()
    results = response.json()
    if not results['items']:
      raise ValueError(f'no GitHub username found for email {email!r}')
    return results['items'][0]['login']


def detect_vcs(path: Path) -> Vcs | None:
  for cls in [Git]:
    if (vcs := cls.detect(path)):
      return vcs
  return None


def detect_vcs_host(path: Path) -> VcsHost | None:
  for cls in [GithubVcsHost]:
    if (vcs := cls.detect(path)):
      return vcs
  return None
