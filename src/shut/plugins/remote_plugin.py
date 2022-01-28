
import abc
import typing as t
from pathlib import Path

from databind.core.annotations import union
from nr.util.plugins import load_plugins

ENTRYPOINT = 'shut.plugins.remote'


@union(
  union.Subtypes.entrypoint(ENTRYPOINT + '_implementation'),
  style=union.Style.flat
)
class Remote(abc.ABC):
  " Interface for Shut plugins that want to provide capabilities for interfacing with the remote repository. "

  @abc.abstractmethod
  def validate_pull_request_url(self, url: str) -> bool: ...

  @abc.abstractmethod
  def get_pull_request_url_from_id(self, pr_id: str) -> str: ...

  @abc.abstractmethod
  def validate_issue_url(self, url: str) -> bool: ...

  @abc.abstractmethod
  def get_issue_url_from_id(self, issue_id: str) -> str: ...

  @abc.abstractmethod
  def get_username_from_email(self, email: str) -> str: ...

  @abc.abstractmethod
  def get_user_profile_url(self, username: str) -> str: ...

  @abc.abstractmethod
  def get_main_branch(self) -> str: ...


class RemotePlugin(abc.ABC):

  @abc.abstractmethod
  def detect(self, directory: Path) -> t.Optional['RemotePlugin']: ...


def detect_remote(directory: Path) -> t.Optional['RemotePlugin']:
  for plugin in load_plugins(ENTRYPOINT, RemotePlugin).values():
    if (remote := plugin.detect(directory)):
      return remote
  return None
