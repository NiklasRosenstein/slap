
""" With the application object we manage the CLI commands and other types of plugins as well as access to the Shut
user and project configuration. """

import abc
import textwrap
import typing as t
from pathlib import Path

from cleo.application import Application as BaseCleoApplication
from cleo.commands.command import Command as _BaseCommand  # type: ignore[import]
from cleo.helpers import argument, option  # type: ignore[import]
from cleo.io.io import IO  # type: ignore[import]
from nr.util import Optional
from nr.util.functional import Once
from nr.util.generic import T
from nr.util.plugins import load_plugins_from_entrypoints, PluginRegistry
from nr.util.fs import get_file_in_directory

from shut import __version__
from shut.util.python_package import Package, detect_packages
from shut.util.toml_file import TomlFile

__all__ = ['Command', 'argument', 'option', 'IO', 'Application', 'ApplicationPlugin']


class Command(_BaseCommand):

  def __init_subclass__(cls) -> None:
    cls.help = textwrap.dedent(cls.help or cls.__doc__ or '')
    cls.description = cls.description or cls.help.strip().splitlines()[0]


class CleoApplication(BaseCleoApplication):

  from cleo.io.inputs.input import Input
  from cleo.io.outputs.output import Output

  def __init__(self, name: str = "console", version: str = "") -> None:
    super().__init__(name, version)
    self._styles = {}

    self._initialized = True
    from shut.commands.help import HelpCommand
    self.add(HelpCommand())
    self._default_command = 'help'

    self.add_style('u', options=['underline'])
    self.add_style('opt', 'cyan', options=['italic'])

  def add_style(self, name, fg=None, bg=None, options=None):
    from cleo.formatters.style import Style
    self._styles[name] = Style(fg, bg, options)

  def create_io(
    self,
    input: Optional[Input] = None,
    output: Optional[Output] = None,
    error_output: Optional[Output] = None
  ) -> IO:
    io = super().create_io(input, output, error_output)
    for style_name, style in self._styles.items():
      io.output.formatter.set_style(style_name, style)
      io.error_output.formatter.set_style(style_name, style)
    return io


class Application:

  DEFAULT_PLUGINS = []

  def __init__(self, project_directory: Path, name: str = 'shut', version: str = __version__) -> None:
    self.project_directory = project_directory
    self.pyproject = TomlFile(project_directory / 'pyproject.toml')
    self.projectcfg = TomlFile(project_directory / 'shut.toml')
    self.usercfg = TomlFile(Path('~/.config/shut/config.toml').expanduser())
    self.raw_config = Once(self.get_raw_configuration)
    self.plugins = PluginRegistry()
    self.cleo = CleoApplication(name, version)

  def get_raw_configuration(self) -> dict[str, t.Any]:
    """ Loads the raw configuration data for Shut from either the `shut.toml` configuration file or `pyproject.toml`
    under the `[shut.tool]` section. If neither of the files exist or the section in the pyproject does not exist,
    an empty dictionary will be returned. """

    if self.projectcfg.exists():
      return self.projectcfg.value()
    if self.pyproject.exists():
      return self.pyproject.value().get('tool', {}).get('shut', {})
    return {}

  def load_plugins(self) -> None:
    """ Loads all application plugins (see {@link ApplicationPlugin}) and activates them.

    By default, all plugins available in the `shut.application.ApplicationPlugin` entry point group are loaded. This
    behaviour can be modified by setting either the `[tool.shut.plugins.disable]` or `[tool.shut.plugins.enable]`
    configuration option (without the `tool.shut` prefix in case of a `shut.toml` configuration file). The default
    plugins delivered immediately with Shut are enabled by default unless disabled explicitly with the `disable`
    option. """

    config = self.raw_config()
    disable: t.Collection[str] | None = config.get('plugins', {}).get('disable')
    enable: t.Collection[str] | None = config.get('plugins', {}).get('enable')
    if enable is not None:
      enable = set(list(enable) + self.DEFAULT_PLUGINS)

    plugins = load_plugins_from_entrypoints('shut.application.ApplicationPlugin', ApplicationPlugin)
    for plugin_name, plugin in plugins.items():
      activate_this_plugin = (
        (enable is None and disable is None) or
        (enable is not None and plugin_name in enable) or
        (disable is not None and plugin_name not in self.DEFAULT_PLUGINS)
      )
      if activate_this_plugin:
        config = plugin.load_configuration(self)
        plugin.activate(self, config)

  def __call__(self) -> None:
    """ Loads and activates application plugins and then invokes the CLI. """

    self.load_plugins()
    self.cleo.run()

  def get_packages(self) -> list[Package]:
    """ Tries to detect the packages in the project directory. Uses `tool.poetry.packages` if that configuration
    exists, otherwise it attempts to automatically determine it. The `tool.shut.source-directory` option is used if
    set, otherwise the `src/` directory or alternatively the project directory is used to detect the packages. """

    source_directory: str | None = self.raw_config().get('source-directory')

    if (directory := Optional(source_directory).map(Path).or_else(None)):
      return detect_packages(Path(directory))

    for directory in [Path('src'), Path()]:
      packages = detect_packages(directory)
      if packages:
        break

    return packages

  def get_readme_path(self) -> Path | None:
    """ Tries to detect the project readme. If `tool.poetry.readme` is set, that file will be returned. """

    # TODO (@NiklasRosenstein): Support other config styles that specify a readme.

    poetry = self.pyproject.value_or({}).get('tool', {}).get('poetry', {})

    if (readme := poetry.get('readme')) and Path(readme).is_file():
      return Path(readme)

    return get_file_in_directory(Path.cwd(), 'README', ['README.md', 'README.rst'], case_sensitive=False)


class ApplicationPlugin(abc.ABC):

  @abc.abstractmethod
  def load_configuration(self, app: Application) -> T: ...

  @abc.abstractmethod
  def activate(self, app: Application, config: T) -> None: ...
