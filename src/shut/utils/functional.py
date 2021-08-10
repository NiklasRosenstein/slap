
import typing as t

T = t.TypeVar('T')


def expect(val: t.Optional[T]) -> T:
  if val is None:
    raise RuntimeError('expected this to not be None')
  return val
