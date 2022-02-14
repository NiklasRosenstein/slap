
import enum
import dataclasses
import typing as t


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
