
import textwrap

from cleo.commands.command import Command as _BaseCommand
from cleo.helpers import argument, option
from cleo.io.io import IO

__all__ = ['Command', 'argument', 'option', 'IO']


class Command(_BaseCommand):

  def __init_subclass__(cls) -> None:
    cls.help = textwrap.dedent(cls.help or cls.__doc__)
