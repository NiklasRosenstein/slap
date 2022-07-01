from __future__ import annotations

import dataclasses
import enum
import inspect
import typing as t

if t.TYPE_CHECKING:
    from slap.application import Application
    from slap.project import Project


class CheckResult(enum.IntEnum):
    OK = enum.auto()
    RECOMMENDATION = enum.auto()
    WARNING = enum.auto()
    ERROR = enum.auto()
    SKIPPED = enum.auto()


@dataclasses.dataclass
class Check:
    Result: t.ClassVar[t.Type[CheckResult]] = CheckResult
    OK: t.ClassVar[CheckResult] = CheckResult.OK
    RECOMMENDATION: t.ClassVar[CheckResult] = CheckResult.RECOMMENDATION
    WARNING: t.ClassVar[CheckResult] = CheckResult.WARNING
    ERROR: t.ClassVar[CheckResult] = CheckResult.ERROR
    SKIPPED: t.ClassVar[CheckResult] = CheckResult.SKIPPED

    name: str
    result: CheckResult
    description: str | None
    details: str | None = None


def check(
    name: str,
) -> t.Callable[
    [
        t.Callable[
            [t.Any, t.Any], CheckResult | tuple[CheckResult, str | None] | tuple[CheckResult, str | None, str | None]
        ]
    ],
    t.Callable[[t.Any, t.Any], Check],
]:
    """Decorator for methods on a #CheckPlugin subclass to mark it as a function that returns detauls for a check.
    That method should return either a #CheckResult, a tuple of a #CheckResult and a description and optionally a
    third element containing more details.

    The second argument of the decorated method _must_ be annotated with either #Project or #Application to deduce
    if this method runs on an application or project.

    Example:

    ```py
    class MyCheckPlugin(CheckPlugin):
      @check("mycheck")
      def get_mycheck(self, project: Project) -> tuple[CheckResult, str]:
        return (CheckResult.OK, 'everything is in order')
    ```

    Use the #get_checks() method to run all methods on an object decorated with this decorator.
    """

    import functools

    from slap.application import Application
    from slap.project import Project

    def decorator(f: t.Callable) -> t.Callable:
        sig = inspect.signature(f)
        subject_type = sig.parameters[list(sig.parameters)[1]].annotation
        if subject_type not in (Project, Application):
            raise ValueError(f"{f} second argument must be annotated with Project or Application, got {subject_type}")

        @functools.wraps(f)
        def wrapper(self, subject) -> Check:
            result = f(self, subject)
            if isinstance(result, CheckResult):
                return Check(name, result, None, None)
            elif isinstance(result, tuple):
                return Check(name, *result)
            elif isinstance(result, Check):
                result.name = name
                return result
            else:
                raise TypeError(f"bad return value for check {name!r}: {result!r}")

        wrapper.__check_name__ = name  # type: ignore
        wrapper.__check_type__ = subject_type  # type: ignore
        return wrapper

    return decorator


def get_checks(obj: t.Any, subject: t.Union[Application, Project]) -> t.Iterable[Check]:
    """Call all methods decorated with #check() on the members of *obj*."""

    for key in dir(obj):
        value = getattr(obj, key)
        check_type = getattr(value, "__check_type__", None)
        if check_type is type(subject):
            yield value(subject)
