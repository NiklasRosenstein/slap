
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
from databind.core.annotations import alias

from slam import __version__

if t.TYPE_CHECKING:
  from nr.util.functional import Once

  from slam.project import Project
  from slam.util.vcs import Vcs

__all__ = ['Command', 'argument', 'option', 'IO', 'Application', 'ApplicationPlugin']
DEFAULT_PLUGINS = ['changelog', 'check', 'link', 'publish', 'release', 'test']
logger = logging.getLogger(__name__)


class Command(_BaseCommand):

  def __init_subclass__(cls) -> None:
    if not cls.help:
      first_line, remainder = (cls.__doc__ or '').partition('\n')[::2]
      cls.help = (first_line.strip() + '\n' + textwrap.dedent(remainder)).strip()
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
    from slam.util.cleo import HelpCommand
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
    input: Input | None = None,
    output: Output | None = None,
    error_output: Output | None = None
  ) -> IO:
    from slam.util.cleo import add_style

    io = super().create_io(input, output, error_output)
    for style_name, style in self._styles.items():
      add_style(io, style_name, style)
    return io

  def render_error(self, error: Exception, io: IO) -> None:
    import subprocess as sp

    if isinstance(error, sp.CalledProcessError):
      msg = 'Uncaught CalledProcessError raised for command <subj>%s</subj> (exit code: <val>%s</val>).'
      args = (error.args[1], error.returncode)
      stdout: str | None = error.stdout.decode() if error.stdout else None
      stderr: str | None = error.stderr.decode() if error.stderr else None
      if stdout:
        msg += '\n  stdout:\n<fg=black;attr=bold>%s</fg>'
        stdout = textwrap.indent(stdout, '    ')
        args += (stdout,)
      if stderr:
        msg += '\n  stderr:\n<fg=black;attr=bold>%s</fg>'
        stderr = textwrap.indent(stderr, '    ')
        args += (stderr,)

      logger.error(msg, *args)

    return super().render_error(error, io)

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
    assert formatter.styles
    formatter.styles.add_style('subj', 'blue')
    formatter.styles.add_style('obj', 'yellow')
    formatter.styles.add_style('val', 'cyan')
    formatter.install()

    self._init_callback()

    return super()._configure_io(io)

  def _run_command(self, command: Command, io: IO) -> int:
    return super()._run_command(command, io)


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

  #: A list of plugins to enable only, causing the default plugins to not be loaded.
  enable_only: t.Annotated[list[str] | None, alias('enable-only')] = None


class Application:
  """ The application object is the main hub for command-line interactions. It is responsible for managing the project
  that is the main subject of the command-line invokation (or multiple of such), provide the {@link cleo} command-line
  application that {@link ApplicationPlugin}s can register commands to, etc. """

  #: A list of projects that are loaded into the application for taking into account by commands.
  #: Multiple projects may be loaded by the application if the first project that is loaded has a {@link
  #: ApplicationConfig.include} configuration.
  projects: list[Project]

  #: The root project identified by {@link get_root_project()}.
  root_project: Once[Project]

  #: The application configuration loaded once via {@link get_application_configuration()}.
  config: Once[ApplicationConfig]

  #: The cleo application to which new commands can be registered via {@link ApplicationPlugin}s.
  cleo: CleoApplication

  #: The version control system that is being used as a {@link Once}.
  vcs: Once[Vcs | None]

  def __init__(self, name: str = 'slam', version: str = __version__) -> None:
    from nr.util.functional import Once

    def _init_app():
      self.load_projects()
      self.load_plugins()

    self._projects_loaded = False
    self._plugins_loaded = False
    self.projects = []
    self.root_project = Once(self.get_root_project)
    self.config = Once(self.get_application_configuration)
    self.cleo = CleoApplication(_init_app, name, version)
    self.vcs = Once(self.get_vcs)

  @property
  def directory(self) -> Path:
    return self.root_project().directory

  @property
  def is_monorepo(self) -> bool:
    return len(self.projects) > 1

  def get_root_project(self) -> Project:
    """ Searches for the root project, by going up the directory tree until the VCS toplevel is reached, taking the
    highest directory that has a `slam.toml` or `pyproject.toml` configuration file. Note that if there is none in
    the current directory or in any of the parent directories, the current directory will be used nonetheless. """

    from nr.util.fs import walk_up

    from slam.project import Project

    vcs = self.vcs()
    toplevel = vcs.get_toplevel().resolve() if vcs else None
    project: Project | None = None

    for path in walk_up(Path.cwd()):
      temp_project = Project(path)
      if temp_project.pyproject_toml.exists() or temp_project.slam_toml.exists():
        project = temp_project
      if path == toplevel:
        break

    if not project:
      project = Project(Path.cwd())

    logger.info('Root project is <subj>%s</subj>', project)
    return project

  def get_application_configuration(self) -> ApplicationConfig:
    """ Loads the application-level configuration. """

    import databind.json
    from databind.core.annotations import enable_unknowns

    return databind.json.load(
      self.root_project().raw_config().get('application', {}),
      ApplicationConfig,
      options=[enable_unknowns()]
    )

  def get_vcs(self) -> Vcs | None:
    """ Detect the version control system in use in the application. """

    from slam.util.vcs import detect_vcs

    assert self._projects_loaded
    vcs = detect_vcs(Path.cwd())
    logger.debug('Detected version control system is <subj>%s</subj>', vcs)
    return vcs

  def get_main_project(self) -> Project:
    """ Returns the main project, which is the one closest to the current working directory. """

    closest: Project | None = None
    distance: int = 99999
    cwd = Path.cwd()

    for project in self.projects:
      path = project.directory.resolve()
      if path == cwd:
        closest = project
        break

      try:
        relative = path.relative_to(cwd)
      except ValueError:
        continue

      if len(relative.parts) < distance:
        closest = project
        distance = len(relative.parts)

    assert closest is not None
    return closest

  def load_projects(self) -> None:
    """ Loads all projects, if any additional aside from the main project need to be loaded. """

    from nr.util.fs import is_relative_to

    from slam.project import Project

    assert not self._projects_loaded
    self._projects_loaded = True

    root = self.root_project()
    self.projects.append(root)

    config = self.config()
    if config.include is None:
      if root.slam_toml.exists() or not root.pyproject_toml.exists():
        # Find immediate subdirectories with a `pyproject.toml` and consider them included.
        for path in root.directory.iterdir():
          if not path.is_dir(): continue
          project = Project(path, root)
          if project.pyproject_toml.exists():
            self.projects.append(project)

    else:
      for path in (root.directory / p for p in config.include):
        self.projects.append(Project(path))

    if self.projects != [root]:
      logger.debug('Loaded projects <subj>%s</subj>', self.projects)

    # Ensure that all loaded projects are inside the VCS toplevel directory.
    vcs = self.vcs()
    if vcs:
      toplevel = vcs.get_toplevel()
      for project in self.projects:
        if not is_relative_to(project.directory, toplevel):
          logger.error(
            'Project <subj>%s</subj> is not relative to the VCS toplevel directory <val>%s</val>',
            self, toplevel
          )
          raise ValueError(f'Project {project} is not relative to the VCS toplevel directory {toplevel!r}')

    if len(set(p.id for p in self.projects)) != len(self.projects):
      raise ValueError(f'Project IDs are not unique')

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

    if config.enable_only is not None:
      plugin_names = set(config.enable_only)
    else:
      plugin_names = set(DEFAULT_PLUGINS) - set(config.disable) | set(config.enable)
    logger.debug('Loading application plugins <subj>%s</subj>', plugin_names)

    for plugin_name in plugin_names:
      try:
        plugin = load_entrypoint(ApplicationPlugin, plugin_name)()  # type: ignore[misc]
      except Exception:
        logger.exception('Could not load plugin <subj>%s</subj> due to an exception', plugin_name)
      else:
        plugin_config = plugin.load_configuration(self)
        plugin.activate(self, plugin_config)

  def run(self) -> None:
    """ Loads and activates application plugins and then invokes the CLI. """

    self.cleo.run()
