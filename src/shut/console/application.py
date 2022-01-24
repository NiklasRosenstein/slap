
import typing as t
from pathlib import Path

from cleo.application import Application as _CleoApplication  # type: ignore[import]
from nr.util.plugins import load_plugins

from shut import __version__
from shut.plugins.application_plugin import ApplicationPlugin, ENTRYPOINT as APPLICATION_PLUGIN_ENTRYPOINT

__all__ = ['Application']

PYPROJECT_TOML = Path('pyproject.toml')


class Application:
  """ The central management unit for the Shut CLI. """

  def __init__(self) -> None:
    self.cleo = _CleoApplication('shut', __version__)
    self._config_cache: dict[str, t.Any] | None = None

  def load_plugins(self) -> None:
    """ Load all #ApplicationPlugin#s and activate them. """

    for app in load_plugins(APPLICATION_PLUGIN_ENTRYPOINT, ApplicationPlugin):  # type: ignore[misc]  # https://github.com/python/mypy/issues/5374
      app.activate(self)

  def load_pyproject(self, force_reload: bool = False) -> dict[str, t.Any]:
    """ Load the `pyproject.toml` configuration in the current working directory and return it.

    If *force_reload* is `True`, the configuration will be reloaded instead of relying on the cache. """

    import tomli
    if self._config_cache is None or force_reload:
      self._config_cache = tomli.loads(PYPROJECT_TOML.read_text())
    return self._config_cache

  def save_pyproject(self, data: dict[str, t.Any] | None = None) -> None:
    """ Save *data* to the `pyproject.toml` file.

    If *data* is `None`, the internal cache that is initialized with #load_pyproject() will be used. Note
    that this does preserve any style information or comments.

    :raise RuntimeError: If *data* is `None` and #load_pyproject() has not been called before. """

    import tomli_w
    if data is None:
      if self._config_cache is None:
        raise RuntimeError('not internal cache')
      data = self._config_cache
    PYPROJECT_TOML.write_text(tomli_w.dumps(data))

  def __call__(self) -> None:
    self.load_plugins()
    self.cleo.run()


app = Application()
