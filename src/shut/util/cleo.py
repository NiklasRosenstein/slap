
import typing as t

from cleo.io.io import IO  # type: ignore[import]
from cleo.formatters.formatter import Formatter  # type: ignore[import]
from cleo.formatters.style import Style  # type: ignore[import]


@t.overload
def add_style(
  io: IO | Formatter,
  name: str,
  foreground: str | None = None,
  background: str | None = None,
  options: list[str] | None = None,
) -> None: ...


@t.overload
def add_style(
  io: IO | Formatter,
  name: str,
  style: Style,
) -> None: ...


def add_style(
  io: IO | Formatter,
  name: str,
  foreground: str | Style | None = None,
  background: str | None = None,
  options: list[str] | None = None,
) -> None:
  """
  Add a style to a Cleo IO or Formatter instance.
  """

  if isinstance(foreground, Style):
    style = foreground
    assert background is None and options is None
  else:
    style = Style(foreground, background, options)

  if isinstance(io, IO):
    io.output.formatter.set_style(name, style)
    io.error_output.formatter.set_style(name, style)
  elif isinstance(io, Formatter):
    io.set_style(name, style)
  else:
    raise TypeError(f'expected IO|Formatter, got {type(io).__name__}')
