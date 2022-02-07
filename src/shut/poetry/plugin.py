
from shut.application import Application, ApplicationPlugin
from shut.commands.check.api import CheckPlugin
from .checks import PoetryChecksPlugin


class PoetryPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    app.plugins.register(CheckPlugin, 'poetry', PoetryChecksPlugin())
