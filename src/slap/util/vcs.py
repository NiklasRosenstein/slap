
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

from slap.changelog import is_url


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
    """ Return the name of the current branch in the local repository. This is used by Slap to ensure that the user
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
    return get_git_author(self._git.path)

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


def get_git_author(path: Path | None = None) -> Author:
  import subprocess as sp
  git = _Git(path)
  global_ = git.get_toplevel() is not None
  try:
    name = git.get_config('user.name', global_=global_)
    email = git.get_config('user.email', global_=global_)
  except sp.CalledProcessError as exc:
    if exc.returncode != 1:
      raise
    return Author(None, None)
  return Author(name, email)


def detect_vcs(path: Path) -> Vcs | None:
  for cls in [Git]:
    if (vcs := cls.detect(path)):
      return vcs
  return None
