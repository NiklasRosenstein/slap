
from cleo.commands.help_command import HelpCommand as _HelpCommand
from cleo.commands.list_command import ListCommand


class HelpCommand(_HelpCommand, ListCommand):

  arguments = ListCommand.arguments

  def handle(self) -> int:
    self.io.input._arguments['namespace'] = None
    if not self._command:
      return ListCommand.handle(self)
    return _HelpCommand.handle(self)
