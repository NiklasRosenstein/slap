
from cleo.application import Application as _CleoApplication
from nr.util.plugins import load_plugins

from shut import __version__
from shut.plugins.application_plugin import ApplicationPlugin, ENTRYPOINT as APPLICATION_PLUGIN_ENTRYPOINT

__all__ = ['Application']


class Application:

  def __init__(self) -> None:
    self.cleo = _CleoApplication('shut', __version__)

  def load_plugins(self) -> None:
    for app in load_plugins(APPLICATION_PLUGIN_ENTRYPOINT, ApplicationPlugin):
      app.activate(self)

  def __call__(self) -> None:
    self.load_plugins()
    self.cleo.run()


app = Application()
