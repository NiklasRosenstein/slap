
import typing as t
from databind.core import Converter, Context, ConcreteType, Direction
from databind.core.types.schema import ObjectType, dataclass_to_schema
from databind.json.modules.object import ObjectTypeConverter


class StringConverter(Converter):

  def __init__(self, loader: t.Optional[t.Callable[[str], t.Any]] = None) -> None:
    self._loader = loader
    self._fallback = ObjectTypeConverter()

  def convert(self, ctx: Context) -> object:
    assert isinstance(ctx.type, ConcreteType)
    if ctx.direction == Direction.serialize:
      assert isinstance(ctx.value, ctx.type.type)
      return str(ctx.value)
    else:
      if isinstance(ctx.value, t.Mapping):
        return self._fallback.convert(ctx.push(ObjectType(
          dataclass_to_schema(ctx.type.type, ctx.type_hint_adapter), []), ctx.value, None))
      elif not isinstance(ctx.value, str):
        raise ctx.type_error(expected=str)
      if self._loader:
        return self._loader(ctx.value)
      else:
        return ctx.type.type.from_string(ctx.value)
