
import abc
import enum
import dataclasses
import typing as t

if t.TYPE_CHECKING:
  from shut.console.application import Application

ENTRYPOINT = "shut.plugins.check"


class CheckResult(enum.Enum):
  OK = enum.auto()
  WARNING = enum.auto()
  ERROR = enum.auto()
  SKIPPED = enum.auto()


@dataclasses.dataclass
class Check:
  Result: t.ClassVar = CheckResult
  name: str
  result: Result
  description: str | None


class CheckPlugin(abc.ABC):
  """ A plugin to add checks to the `shut check` command. """

  @abc.abstractmethod
  def get_checks(self, app: 'Application') -> t.Iterable[Check]: ...
