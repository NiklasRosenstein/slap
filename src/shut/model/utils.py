
import typing as t
from databind.core import Converter, Context, ConcreteType, Direction


class StringConverter(Converter):

  def __init__(self, loader: t.Optional[t.Callable[[str], t.Any]] = None) -> None:
    self._loader = loader

  def convert(self, ctx: Context) -> object:
    assert isinstance(ctx.type, ConcreteType)
    if ctx.direction == Direction.serialize:
      assert isinstance(ctx.value, ctx.type.type)
      return str(ctx.value)
    else:
      if not isinstance(ctx.value, str):
        raise ctx.type_error(expected=str)
      if self._loader:
        return self._loader(ctx.value)
      else:
        return ctx.type.type.from_string(ctx.value)
