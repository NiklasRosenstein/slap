
from lib2to3.refactor import get_all_fix_names
import typing as t
from pathlib import Path

from cleo.application import Application as _CleoApplication  # type: ignore[import]
from nr.util import Optional
from nr.util.plugins import load_plugins

from shut import __version__
from shut.core.config import ProjectConfig, GlobalConfig
from shut.core.raw_config import RawConfig
from shut.core.toml_config import TomlConfig
from shut.plugins.application_plugin import ApplicationPlugin, ENTRYPOINT as APPLICATION_PLUGIN_ENTRYPOINT
from shut.plugins.remote_plugin import RemotePlugin, detect_remote
from shut.plugins.plugin_registry import PluginRegistry
from shut.util.python_package import Package, detect_packages
from shut.util.fs import get_file_in_directory

__all__ = ['Application']


class Application:
  """ The central management unit for the Shut CLI. """

  def __init__(self, project_dir: Path | None = None) -> None:
    self.cleo = _CleoApplication('shut', __version__)
    self._raw_config = RawConfig(project_dir or Path.cwd())
    self._remote: RemotePlugin | None = None
    self._registries: dict[str, PluginRegistry] = {}

  def load_plugins(self) -> None:
    """ Load all #ApplicationPlugin#s and activate them. """

    for plugin in load_plugins(APPLICATION_PLUGIN_ENTRYPOINT, ApplicationPlugin).values():  # type: ignore[misc]  # https://github.com/python/mypy/issues/5374
        config = plugin.load_config(self)
        plugin.activate(self, config)

  def registry(self, registry_id: str) -> PluginRegistry:
    return self._registries.setdefault(registry_id, PluginRegistry())

  @property
  def pyproject(self) -> TomlConfig:
    return self._raw_config.pyproject

  @property
  def project_config(self) -> ProjectConfig:
    import databind.json
    data = self.load_pyproject().get('tool', {}).get('shut', {})
    return databind.json.load(data, ProjectConfig)

  @property
  def global_config(self) -> GlobalConfig:
    import databind.json
    data = self.load_global_config()
    return databind.json.load(data, GlobalConfig)

  @property
  def remote(self) -> RemotePlugin | None:
    if self._remote is None:
      self._remote = self.project_config.remote or detect_remote(Path.cwd())
    return self._remote

  def get_packages(self) -> list[Package]:
    """ Tries to detect the packages in the project directory. Uses `tool.poetry.packages` if that configuration
    exists, otherwise it attempts to automatically determine it. The `tool.shut.source-directory` option is used
    if set, otherwise the `src/` directory or alternatively the project directory is used to detect the packages.
    """

    if (directory := Optional(self.project_config.source_directory).map(Path).or_else(None)):
      return detect_packages(Path(directory))

    for directory in [Path('src'), Path()]:
      packages = detect_packages(directory)
      if packages:
        break

    return packages

  def get_readme_path(self) -> Path | None:
    """ Tries to detect the project readme. If `tool.poetry.readme` is set, that file will be returned. """

    if (readme := self.load_pyproject().get('tool', {}).get('poetry', {}).get('readme')) and Path(readme).is_file():
      return Path(readme)

    return get_file_in_directory(Path.cwd(), 'README', ['README.md', 'README.rst'], case_sensitive=False)

  def __call__(self) -> None:
    self.load_plugins()
    self.cleo.run()


app = Application()
