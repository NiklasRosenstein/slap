
""" With the application object we manage the CLI commands and other types of plugins as well as access to the Slam
user and project configuration. """

from __future__ import annotations

import dataclasses
import logging
import textwrap
import typing as t
from pathlib import Path

from cleo.application import Application as BaseCleoApplication  # type: ignore[import]
from cleo.commands.command import Command as _BaseCommand  # type: ignore[import]
from cleo.helpers import argument, option  # type: ignore[import]
from cleo.io.inputs.argument import Argument  # type: ignore[import]
from cleo.io.inputs.option import Option  # type: ignore[import]
from cleo.io.io import IO  # type: ignore[import]
from nr.util import Optional
from nr.util.functional import Once

from slam import __version__
from slam.util.cleo import add_style
from slam.util.vcs import Vcs, detect_vcs

from slam.project import Project

if t.TYPE_CHECKING:
  from nr.util.functional import Once

logger = logging.getLogger(__name__)
__all__ = ['Command', 'argument', 'option', 'IO', 'Application', 'ApplicationPlugin']


class Command(_BaseCommand):

  def __init_subclass__(cls) -> None:
    cls.help = textwrap.dedent(cls.help or cls.__doc__ or '')
    cls.description = cls.description or cls.help.strip().splitlines()[0]

    # TODO (@NiklasRosenstein): Implement automatic wrapping of description text, but we
    #   need to ignore HTML tags that are used to colour the output.

    # argument: Argument
    # for argument in cls.arguments:
    #   print(argument)
    #   argument._description = '\n'.join(textwrap.wrap(argument._description or '', 70))

    # option: Option
    # for option in cls.options:
    #   print(option)
    #   option._description = '\n'.join(textwrap.wrap(option._description or '', 70))


class CleoApplication(BaseCleoApplication):

  from cleo.io.inputs.input import Input  # type: ignore[import]
  from cleo.io.outputs.output import Output  # type: ignore[import]
  from cleo.formatters.style import Style  # type: ignore[import]

  _styles: dict[str, Style]

  def __init__(self, init: t.Callable[[], t.Any], name: str = "console", version: str = "") -> None:
    super().__init__(name, version)
    self._init_callback = init
    self._styles = {}

    self._initialized = True
    from slam.commands.help import HelpCommand
    self.add(HelpCommand())
    self._default_command = 'help'

    self.add_style('code', 'dark_gray')
    self.add_style('warning', 'magenta')
    self.add_style('u', options=['underline'])
    self.add_style('i', options=['italic'])
    self.add_style('s', 'yellow')
    self.add_style('opt', 'cyan', options=['italic'])

  def add_style(self, name, fg=None, bg=None, options=None):
    self._styles[name] = self.Style(fg, bg, options)

  def create_io(
    self,
    input: Optional[Input] = None,
    output: Optional[Output] = None,
    error_output: Optional[Output] = None
  ) -> IO:
    io = super().create_io(input, output, error_output)
    for style_name, style in self._styles.items():
      add_style(io, style_name, style)
    return io

  def _configure_io(self, io: IO) -> None:
    import logging

    from nr.util.logging.formatters.terminal_colors import TerminalColorFormatter

    if io.input.has_parameter_option("-vvv") or io.input.has_parameter_option("-vv"):
      level = logging.DEBUG
    elif io.input.has_parameter_option("-v"):
      level = logging.INFO
    elif io.input.has_parameter_option("-q"):
      level = logging.ERROR
    elif io.input.has_parameter_option("-qq"):
      level = logging.CRITICAL
    else:
      level = logging.WARNING

    logging.basicConfig(level=level)
    formatter = TerminalColorFormatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
    formatter.styles.add_style('subj', 'blue')
    formatter.styles.add_style('obj', 'yellow')
    formatter.styles.add_style('val', 'cyan')
    formatter.install()

    self._init_callback()

    return super()._configure_io(io)


DEFAULT_PLUGINS = ['check', 'link', 'log', 'release', 'test', 'poetry', 'github']


@dataclasses.dataclass
class ApplicationConfig:
  #: A list of paths pointing to projects to include in the application invokation. This is useful if multuple
  #: projects should be usable with the Slam CLI in unison. Note that if this option is not set and either no
  #: configuration file exists in the CWD or the `slam.toml` is used, all immediate subdirectories that contain
  #: a `pyproject.toml` will be considered included projects.
  include: list[str] | None = None

  #: A list of plugins to disable from the {@link DEFAULT_PLUGINS}.
  disable: list[str] = dataclasses.field(default_factory=list)

  #: A list of plugins to enable in addition to the {@link DEFAULT_PLUGINS}.
  enable: list[str] = dataclasses.field(default_factory=list)


class Application:
  """ The application object is the main hub for command-line interactions. It is responsible for managing the project
  that is the main subject of the command-line invokation (or multiple of such), provide the {@link cleo} command-line
  application that {@link ApplicationPlugin}s can register commands to, etc. """

  #: A list of projects that are loaded into the application for taking into account by commands.
  #: Multiple projects may be loaded by the application if the first project that is loaded has a {@link
  #: ApplicationConfig.include} configuration.
  projects: list[Project]

  #: The application configuration loaded once via {@link get_application_configuration()}.
  config: Once[ApplicationConfig]

  #: The cleo application to which new commands can be registered via {@link ApplicationPlugin}s.
  cleo: CleoApplication

  #: The version control system that is being used as a {@link Once}.
  vcs: Once[Vcs | None]

  def __init__(self, name: str = 'slam', version: str = __version__) -> None:
    from nr.util.functional import Once

    self._projects_loaded = False
    self._plugins_loaded = False
    self._main_project = Project(Path('.'))
    self.projects = [self._main_project]
    self.config = Once(self.get_application_configuration)
    self.cleo = CleoApplication(lambda: [self.load_projects(), self.load_plugins()], name, version)
    self.vcs = Once(self.get_vcs)

  @property
  def directory(self) -> Path:
    return self._main_project.directory

  def get_application_configuration(self) -> ApplicationConfig:
    """ Loads the application-level configuration. """

    import databind.json
    from databind.core.annotations import enable_unknowns
    return databind.json.load(self._main_project.raw_config(), ApplicationConfig, options=[enable_unknowns()])

  def get_vcs(self) -> Vcs | None:
    """ Detect the version control system in use in the application. """

    from nr.util.fs import is_relative_to

    assert self._projects_loaded
    vcs = detect_vcs(self.directory)
    logger.debug('Detected version control system is <subj>%s</subj>', vcs)
    if vcs:
      toplevel = vcs.get_toplevel()
      for project in self.projects:
        if not is_relative_to(project.directory, toplevel):
          logger.error(
            'Project <subj>%s</subj> is not relative to the VCS toplevel directory <val>%s</val>',
            self, toplevel
          )
          raise ValueError(f'Project {project} is not relative to the VCS toplevel directory {toplevel!r}')

    return vcs

  def load_projects(self) -> None:
    """ Loads all projects, if any additional aside from the main project need to be loaded. """

    assert not self._projects_loaded
    self._projects_loaded = True

    config = self.config()
    if config.include is None:
      if self._main_project.slam_toml.exists() or not self._main_project.pyproject_toml.exists():
        # Find immediate subdirectories with a `pyproject.toml` and consider them included.
        for path in self._main_project.directory.iterdir():
          if not path.is_dir(): continue
          project = Project(path)
          if project.pyproject_toml.exists():
            self.projects.append(project)

    else:
      for path in (self._main_project.directory / p for p in config.include):
        self.projects.append(Project(path))

    logger.debug('Loaded projects <subj>%s</subj>', self.projects)

  def load_plugins(self) -> None:
    """ Loads all application plugins (see {@link ApplicationPlugin}) and activates them.

    By default, all plugins available in the `slam.application.ApplicationPlugin` entry point group are loaded. This
    behaviour can be modified by setting either the `[tool.slam.plugins.disable]` or `[tool.slam.plugins.enable]`
    configuration option (without the `tool.slam` prefix in case of a `slam.toml` configuration file). The default
    plugins delivered immediately with Slam are enabled by default unless disabled explicitly with the `disable`
    option. """

    from nr.util.plugins import load_entrypoint

    from slam.plugins import ApplicationPlugin

    assert not self._plugins_loaded
    self._plugins_loaded = True

    config = self.config()

    plugin_names = set(DEFAULT_PLUGINS) - set(config.disable) | set(config.enable)
    logger.debug('Loading application plugins <subj>%s</subj>', plugin_names)

    for plugin_name in plugin_names:
      if plugin_name != 'link': continue
      plugin = load_entrypoint(ApplicationPlugin, plugin_name)()
      plugin_config = plugin.load_configuration(self)
      plugin.activate(self, plugin_config)

  def run(self) -> None:
    """ Loads and activates application plugins and then invokes the CLI. """

    self.cleo.run()
