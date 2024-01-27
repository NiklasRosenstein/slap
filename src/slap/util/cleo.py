import typing as t

from cleo.commands.help_command import HelpCommand as _HelpCommand  # type: ignore[import]
from cleo.commands.list_command import ListCommand  # type: ignore[import]
from cleo.formatters.formatter import Formatter  # type: ignore[import]
from cleo.formatters.style import Style  # type: ignore[import]
from cleo.io.io import IO  # type: ignore[import]


@t.overload
def add_style(
    io: IO | Formatter,
    name: str,
    foreground: str | None = ...,
    background: str | None = ...,
    options: list[str] | None = ...,
) -> None: ...


@t.overload
def add_style(
    io: IO | Formatter,
    name: str,
    style: Style,
) -> None: ...


def add_style(  # type: ignore[misc]
    io: IO | Formatter,
    name: str,
    foreground: str | Style | None = None,
    background: str | None = None,
    options: list[str] | None = None,
    *,
    style: Style | None = None,
) -> None:
    """
    Add a style to a Cleo IO or Formatter instance.
    """

    if style is not None:
        assert foreground is None and background is None and options is None
    elif isinstance(foreground, Style):
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
        raise TypeError(f"expected IO|Formatter, got {type(io).__name__}")


class HelpCommand(_HelpCommand, ListCommand):
    arguments = ListCommand.arguments

    def handle(self) -> int:
        self.io.input._arguments["namespace"] = None
        if not self._command:
            return ListCommand.handle(self)
        return _HelpCommand.handle(self)
