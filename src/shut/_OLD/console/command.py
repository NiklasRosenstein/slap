
import textwrap

from cleo.commands.command import Command as _BaseCommand  # type: ignore[import]
from cleo.helpers import argument, option  # type: ignore[import]
from cleo.io.io import IO  # type: ignore[import]

__all__ = ['Command', 'argument', 'option', 'IO']


class Command(_BaseCommand):

  def __init_subclass__(cls) -> None:
    cls.help = textwrap.dedent(cls.help or cls.__doc__ or '')
