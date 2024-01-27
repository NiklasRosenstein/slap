""" With the application object we manage the CLI commands and other types of plugins as well as access to the Slap
user and project configuration. """

from __future__ import annotations

import dataclasses
import logging
import subprocess as sp
import textwrap
import typing as t
from pathlib import Path

from cleo.application import Application as BaseCleoApplication  # type: ignore[import]
from cleo.commands.command import Command as _BaseCommand  # type: ignore[import]
from cleo.helpers import argument, option  # type: ignore[import]
from cleo.io.io import IO  # type: ignore[import]
from databind.core.settings import Alias

from slap import __version__
from slap.util.strings import split_by_commata

if t.TYPE_CHECKING:
    from slap.configuration import Configuration
    from slap.project import Project
    from slap.repository import Repository
    from slap.util.once import Once

__all__ = ["Command", "argument", "option", "IO", "Application"]
logger = logging.getLogger(__name__)


class Command(_BaseCommand):
    help: str
    description: str

    def __init_subclass__(cls) -> None:
        if not cls.help:
            first_line, remainder = (cls.__doc__ or "").partition("\n")[::2]
            cls.help = (first_line.strip() + "\n" + textwrap.dedent(remainder)).strip()
        cls.description = cls.description or (cls.help.strip().splitlines()[0] if cls.help else None) or ""

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
    from cleo.formatters.style import Style  # type: ignore[import]
    from cleo.io.inputs.input import Input  # type: ignore[import]
    from cleo.io.outputs.output import Output  # type: ignore[import]

    _styles: dict[str, Style]

    def __init__(self, init: t.Callable[[IO], t.Any], name: str = "console", version: str = "") -> None:
        super().__init__(name, version)
        self._init_callback = init
        self._styles = {}

        self._initialized = True
        from slap.util.cleo import HelpCommand

        self.add(HelpCommand())
        self._default_command = "help"

        self.add_style("code", "dark_gray")
        self.add_style("warning", "magenta")
        self.add_style("u", options=["underline"])
        self.add_style("i", options=["italic"])
        self.add_style("s", "yellow")
        self.add_style("opt", "cyan", options=["italic"])

    def add_style(self, name, fg=None, bg=None, options=None):
        self._styles[name] = self.Style(fg, bg, options)

    def create_io(
        self, input: Input | None = None, output: Output | None = None, error_output: Output | None = None
    ) -> IO:
        from slap.util.cleo import add_style

        io = super().create_io(input, output, error_output)
        for style_name, style in self._styles.items():
            add_style(io, style_name, style)
        return io

    def render_error(self, error: Exception, io: IO) -> None:
        import subprocess as sp

        if isinstance(error, sp.CalledProcessError):
            msg = "Uncaught CalledProcessError raised for command <subj>%s</subj> (exit code: <val>%s</val>)."
            args: tuple[t.Any, ...] = (error.args[1], error.returncode)
            stdout: str | None = error.stdout.decode() if error.stdout else None
            stderr: str | None = error.stderr.decode() if error.stderr else None
            if stdout:
                msg += "\n  stdout:\n<fg=black;attr=bold>%s</fg>"
                stdout = textwrap.indent(stdout, "    ")
                args += (stdout,)
            if stderr:
                msg += "\n  stderr:\n<fg=black;attr=bold>%s</fg>"
                stderr = textwrap.indent(stderr, "    ")
                args += (stderr,)

            logger.error(msg, *args)

        return super().render_error(error, io)

    def _configure_io(self, io: IO) -> None:
        import logging

        from slap.util.logging import TerminalColorFormatter

        fmt = "<fg=bright black>%(message)s</fg>"
        if io.input.has_parameter_option("-vvv"):
            fmt = "<fg=bright black>%(asctime)s | %(levelname)s | %(name)s | %(message)s</fg>"
            level = logging.DEBUG
        elif io.input.has_parameter_option("-vv"):
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
        formatter = TerminalColorFormatter(fmt)
        assert formatter.styles
        formatter.styles.add_style("subj", "blue")
        formatter.styles.add_style("obj", "yellow")
        formatter.styles.add_style("val", "cyan")
        formatter.install("tty")
        formatter.install("notty")  # Hack for now to enable it also in CI

        super()._configure_io(io)
        self._init_callback(io)

    def _run_command(self, command: Command, io: IO) -> int:  # type: ignore[override]
        return super()._run_command(command, io)


@dataclasses.dataclass
class ApplicationConfig:
    #: A list of application plugins to _not_ activate.
    disable: list[str] = dataclasses.field(default_factory=list)

    #: A list of plugins to enable only, causing the default plugins to not be loaded.
    enable_only: t.Annotated[list[str] | None, Alias("enable-only")] = None


class Application:
    """The application object is the main hub for command-line interactions. It is responsible for managing the project
    that is the main subject of the command-line invokation (or multiple of such), provide the #cleo command-line
    application that #ApplicationPlugin#s can register commands to, etc."""

    main_project: Once[Project | None]

    #: The application configuration loaded once via #get_application_configuration().
    config: Once[ApplicationConfig]

    #: The cleo application to which new commands can be registered via #ApplicationPlugin#s.
    cleo: CleoApplication

    def __init__(self, directory: Path | None = None, name: str = "slap", version: str = __version__) -> None:
        from slap.util.once import Once

        self._directory = directory or Path.cwd()
        self._repository: t.Optional[Repository] = None
        self._plugins_loaded = False
        self.config = Once(self._get_application_configuration)
        self.cleo = CleoApplication(self._cleo_init, name, version)
        self.main_project = Once(self._get_main_project)

    @property
    def repository(self) -> Repository:
        """Return the Slap repository that is the subject of the current application. There may be command plugins
        that do not require the repository to function, so this property creates the repository lazily."""

        if self._repository is None:
            self._repository = find_repository(self._directory)

        return self._repository

    def _get_application_configuration(self) -> ApplicationConfig:
        """Loads the application-level configuration."""

        from databind.core.settings import ExtraKeys
        from databind.json import load

        raw_config = self.repository.raw_config().get("application", {})
        return load(raw_config, ApplicationConfig, settings=[ExtraKeys(True)])

    def _get_main_project(self) -> Project | None:
        """Returns the main project, which is the one that the current working directory is pointing to."""

        cwd = Path.cwd()

        for project in self.repository.projects():
            path = project.directory.resolve()
            if path == cwd:
                return project

        return None

    def configurations(self, targets_only: bool = False) -> list[Configuration]:
        """Return a list of all configuration objects, i.e. all projects and eventually the #Repository, unless one
        project is from the same directory as the repository."""

        result: list[Configuration] = list(self.get_target_projects() if targets_only else self.repository.projects())
        if self.repository.directory not in tuple(p.directory for p in self.repository.projects()):
            result.insert(0, self.repository)
        return result

    def load_plugins(self) -> None:
        """Loads all application plugins (see #ApplicationPlugin) and activates them.

        By default, all plugins available in the `slap.application.ApplicationPlugin` entry point group are loaded. This
        behaviour can be modified by setting either the `[tool.slap.plugins.disable]` or `[tool.slap.plugins.enable]`
        configuration option (without the `tool.slap` prefix in case of a `slap.toml` configuration file). The default
        plugins delivered immediately with Slap are enabled by default unless disabled explicitly with the `disable`
        option."""

        from slap.plugins import ApplicationPlugin
        from slap.util.plugins import iter_entrypoints

        assert not self._plugins_loaded
        self._plugins_loaded = True

        config = self.config()
        disable = config.disable or []

        logger.debug("Loading application plugins")

        for plugin_name, loader in iter_entrypoints(ApplicationPlugin):  # type: ignore[type-abstract]
            if plugin_name in disable:
                continue
            try:
                plugin = loader()(self)
            except Exception:
                logger.exception("Could not load plugin <subj>%s</subj> due to an exception", plugin_name)
            else:
                plugin_config = plugin.load_configuration(self)
                plugin.activate(self, plugin_config)

    def _cleo_init(self, io: IO) -> None:
        self.load_plugins()

    def run(self) -> None:
        """Loads and activates application plugins and then invokes the CLI."""

        self.cleo.run()

    def get_target_projects(
        self, only_projects: str | t.Sequence[str] | None = None, cwd: Path | None = None
    ) -> list[Project]:
        """
        Returns the list of projects that should be dealt with when executing a command. When there is a main project,
        only the main project will be returned. When in the repository root, all projects will be returned.
        """

        cwd = cwd or self._directory
        if isinstance(only_projects, str):
            only_projects = split_by_commata(only_projects)

        if only_projects is not None:
            projects: list[Project] = []
            for only_project in only_projects:
                project_path = (cwd / only_project).resolve()
                matching_projects = [p for p in self.repository.projects() if p.directory.resolve() == project_path]
                if not matching_projects:
                    raise ValueError(f'error: "{only_project}" does not point to a project')
                projects += matching_projects
            return projects

        main = self.main_project()
        if main:
            return [main]
        if cwd == self.repository.directory:
            return self.repository.get_projects_ordered()
        return []


def find_repository(directory: Path) -> Repository:
    """
    Finds the repository for the given directory. This will search for the closest parent directory that contains a
    `slap.toml` configuration file. If no such file exists, but we're in a Git directory, and the given *directory*
    is not the Git root directory, then a warning is printed and the *directory* is assumed to be the Slap repository
    root.
    """

    from slap.repository import Repository

    directory = directory.resolve()

    try:
        git_root = Path(
            sp.check_output(["git", "rev-parse", "--show-toplevel"], cwd=directory, stderr=sp.STDOUT).decode().strip()
        )
    except sp.CalledProcessError:
        git_root = None

    if git_root is not None and git_root != directory:
        directory.relative_to(git_root)  # Raises ValueError if not a sub directory

        curdir = directory
        while True:
            if (curdir / "slap.toml").is_file():
                return Repository(curdir)
            if curdir == git_root:
                break
            curdir = curdir.parent

        logger.warning(
            "Could not find a <subj>slap.toml</subj> configuration file in the current directory or any of its "
            "parents. Assuming that the current directory is the Slap repository root."
        )

    return Repository(directory)
