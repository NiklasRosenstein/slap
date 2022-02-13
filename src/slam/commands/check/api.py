
import abc
import enum
import dataclasses
import typing as t

if t.TYPE_CHECKING:
  from slam.application import Application


class CheckResult(enum.IntEnum):
  OK = enum.auto()
  RECOMMENDATION = enum.auto()
  WARNING = enum.auto()
  ERROR = enum.auto()
  SKIPPED = enum.auto()


@dataclasses.dataclass
class Check:
  Result: t.ClassVar = CheckResult
  OK: t.ClassVar = CheckResult.OK
  RECOMMENDATION: t.ClassVar = CheckResult.RECOMMENDATION
  WARNING: t.ClassVar = CheckResult.WARNING
  ERROR: t.ClassVar = CheckResult.ERROR
  SKIPPED: t.ClassVar = CheckResult.SKIPPED

  name: str
  result: Result
  description: str | None
  details: str | None = None


class CheckPlugin(abc.ABC):
  """ A plugin to add checks to the `slam check` command. """

  @abc.abstractmethod
  def get_checks(self, app: 'Application') -> t.Iterable[Check]: ...
