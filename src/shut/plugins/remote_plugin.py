
import abc

from databind.core.annotations import union

ENTRYPOINT = 'shut.plugins.remote'


@union(
  union.Subtypes.entrypoint(ENTRYPOINT),
  style=union.Style.flat
)
class RemotePlugin(abc.ABC):
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
