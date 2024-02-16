from __future__ import annotations

import dataclasses
import logging
import os
import typing as t
from pathlib import Path

import typing_extensions as te
from databind.core.settings import Alias, ExtraKeys

from slap.application import Application, Command, option
from slap.configuration import Configuration
from slap.ext.application.venv import UvVenv, VenvAwareCommand
from slap.plugins import ApplicationPlugin
from slap.project import Project

if t.TYPE_CHECKING:
    from slap.install.installer import Indexes
    from slap.python.dependency import Dependency
    from slap.python.environment import PythonEnvironment


logger = logging.getLogger(__name__)

python_option = option(
    "--python",
    "-p",
    description="The Python executable to install to.",
    flag=False,
)


@t.overload
def get_active_python_bin(cmd: Command) -> str: ...


@t.overload
def get_active_python_bin(cmd: Command, fallback: te.Literal[False]) -> str | None: ...


def get_active_python_bin(cmd: Command, fallback: bool = True) -> str | None:
    """Returns the active Python installation."""

    if hasattr(cmd, "_python_bin"):
        python = cmd._python_bin  # type: ignore[attr-defined]
    else:
        python = cmd.option("python")
        if not python:
            python = os.getenv("PYTHON")
    if fallback:
        python = python or "python"
    cmd._python_bin = python  # type: ignore[attr-defined]
    return python


def venv_check(cmd: Command, message="refusing to install", env: PythonEnvironment | None = None) -> bool:
    from slap.python.environment import PythonEnvironment

    if not cmd.option("no-venv-check"):
        env = env or PythonEnvironment.of(get_active_python_bin(cmd))
        if not env.is_venv():
            cmd.line_error(f"error: {message} because you are not in a virtual environment", "error")
            cmd.line_error("       enter a virtual environment or use <opt>--no-venv-check</opt>", "error")
            cmd.line_error(f"       the Python executable you are targeting is <s>{env.executable}</s>", "error")
            return False
    return True


@dataclasses.dataclass
@ExtraKeys(True)
class InstallConfig:
    """Separate install configuration under Slap that is entirely separate from the build system that is being used.
    This configures the behaviour of the `slap install` command."""

    #: Additional extras that are installable with `--extras` or `--only-extras`. These are taken into account
    #: for projects as well as the mono-repository root. They may contain semantic version selector (same style
    #: as supported by Poetry).
    extras: dict[str, list[str]] = dataclasses.field(default_factory=dict)

    #: A list of extra names to install in addition to `dev` when using `slap install` (unless `--no-dev` is
    #: specified). If this option is not set, _all_ extras are installed.
    dev_extras: t.Annotated[list[str] | None, Alias("dev-extras")] = None


class InstallCommandPlugin(VenvAwareCommand, ApplicationPlugin):
    """Install your project and its dependencies via Pip."""

    app: Application
    name = "install"
    options = VenvAwareCommand.options + [
        option(
            "--installer",
            description="The installer to use. Defaults to Pip for normal normal venvs, and UV for "
            "UV-created venvs. [pip|uv]",
            default=None,
            flag=False,
        ),
        option(
            "--only",
            description="Path to the subproject to install only. May still cause other projects to be installed if "
            "required by the selected project via inter dependencies, but only their run dependencies will be "
            "installed.",
            flag=False,
        ),
        option(
            "--link",
            description="Symlink the root project using <opt>slap link</opt> instead of installing it directly.",
        ),
        option(
            "--no-dev",
            description="Do not install development dependencies.",
        ),
        option(
            "--no-root",
            description="Do not install the package itself, but only its dependencies.",
        ),
        option(
            "--extras",
            description='A comma-separated list of extras to install. Note that <s>"dev"</s> is a valid extras.',
            flag=False,
        ),
        option(
            "--only-extras",
            description='Install only the specified extras. Note that <s>"dev"</s> is a valid extras.',
            flag=False,
        ),
        option(
            "--upgrade",
            description="Upgrade already installed packages.",
            flag=True,
        ),
        option(
            "--from",
            description="Install another Slap project from the given directory.",
            flag=False,
        ),
        option(
            "--index",
            description="Set an index URL to install from. Must be formatted like <s>name=myindex,url=https://...</s> "
            "The username and password may be specified as arguments as well. Note that this format requires "
            "that commas are urlencoded if they are presented in the URL. This argument can be used to override the "
            "URL of the index that a dependency is installed from (the dependency must specify a `source` in "
            "`pyproject.toml`) and/or inject credentials.",
            flag=False,
            multiple=True,
        ),
        option(
            "--extra-index",
            description="Deprecated. Same as --index.",
            flag=False,
            multiple=True,
        ),
        python_option,
    ]

    def load_configuration(self, app: Application) -> None:
        from databind.json import load

        self.config: dict[Configuration, InstallConfig] = {}
        for obj in app.configurations():
            self.config[obj] = load(obj.raw_config().get("install", {}), InstallConfig, filename=str(obj))
        return None

    def activate(self, app: Application, config: None) -> None:
        self.app = app
        app.cleo.add(self)

    def handle(self) -> int:
        """
        Installs the requirements of the package using Pip.
        """

        from nr.stream import Stream

        from slap.install.installer import InstallOptions, PipInstaller, get_indexes_for_projects
        from slap.python.dependency import PathDependency, PypiDependency, parse_dependencies
        from slap.python.environment import PythonEnvironment

        if not self._validate_args():
            return 1

        result = super().handle()
        if result != 0:
            return result

        if from_dir := self.option("from"):
            # TODO (@NiklasRosenstein): This is pretty hacky, but it works so far. We basically modify the application
            #       object as if it was running from the specified path all along.
            self.app.__init__(Path(from_dir).absolute())  # type: ignore
            self.app.load_plugins()
            self.load_configuration(self.app)

        python_environment = PythonEnvironment.of(get_active_python_bin(self))
        if not venv_check(self, env=python_environment):
            return 1

        projects = self._get_projects_to_install()
        if not projects:
            return 1

        # Get a list of the projects that need to be installed that also includes all the projects required through
        # interdependencies between the projects.
        projects_plus_dependencies = (
            Stream(projects)
            .map(lambda p: p.get_interdependencies(self.app.repository.projects(), recursive=True))
            .concat()
            .append(projects)
            .distinct()
            .collect()
        )

        install_extras = self._get_extras_to_install()
        discovered_extras = {"dev"}  # Not discovering a 'dev' extra should not trigger a warning
        dependencies: list[Dependency] = []

        # Collect the run dependencies to install.
        for project in projects_plus_dependencies:
            assert project.is_python_project, "Project.is_python_project is deprecated and expected to always be true"
            deps = project.dependencies()

            if (
                not self.option("no-root")
                and not self.option("link")
                and not self.option("only-extras")
                and project.packages()
            ):
                # Install the project itself directory unless certain flags turn this behavior off.
                dependencies.append(PathDependency(project.dist_name() or project.id, project.directory))

            elif not self.option("only-extras"):
                # Install the run dependencies of the project.
                dependencies += deps.run

        # Collect dev dependencies and extras from the project.
        for project in projects:
            deps = project.dependencies()

            if (not self.option("no-dev") and not self.option("only-extras")) or "dev" in install_extras:
                # Install the development dependencies of the project.
                dependencies += deps.dev

            # Determine the extras to install for the current project. This changes on development installs because
            # we always consider the ones configured in #InstallConfig.dev_extras.
            current_project_install_extras = set(install_extras)
            if not self.option("no-dev"):
                config = self.config[project]
                if config.dev_extras is not None:
                    current_project_install_extras.update(config.dev_extras)

            # Append the extra dependencies from the project. We ignore 'dev' here because we already took care of
            # deciding when to install dev dependencies.
            for extra in current_project_install_extras:
                extra_deps = deps.extra.get(extra)
                if extra_deps is not None:
                    discovered_extras.add(extra)
                    dependencies += extra_deps

        # Look for extras also in the Slap specific install configuration.
        for _, config in self.config.items():
            for extra in install_extras:
                dependencies += parse_dependencies(config.extras.get(extra, []))
                discovered_extras.add(extra)

        if missing_extras := install_extras - discovered_extras:
            self.line_error(f"error: extras that do not exist: <fg=yellow>{missing_extras}</fg>", "error")
            return 1

        # Remove dependencies that reference projects in the same mono repository, as we are installing them separately.
        project_names = {project.dist_name() for project in projects_plus_dependencies}
        dependencies = [
            dependency
            for dependency in dependencies
            if not (isinstance(dependency, PypiDependency) and dependency.name in project_names)
        ]

        if not dependencies:
            self.line("nothing to install.", "info")
            return 0

        options = InstallOptions(
            indexes=get_indexes_for_projects(projects),
            quiet=self.option("quiet"),
            upgrade=self.option("upgrade"),
        )
        self._update_indexes_from_cli(options.indexes)

        if installer := self.option("installer"):
            use_uv = installer == "uv"
        else:
            if not self.current_venv:
                self.line_error("warning: no virtual environment detected, using Pip installer")
                use_uv = False
            elif isinstance(self.current_venv, UvVenv):
                use_uv = True
            else:
                use_uv = False

        installer = PipInstaller(use_uv=use_uv, symlink_helper=self)
        status_code = installer.install(dependencies, python_environment, options)
        if status_code != 0:
            return status_code

        if self.option("link"):
            self._link_projects(projects_plus_dependencies)

        return 0

    def _validate_args(self) -> bool:
        """Validate combinations of command-line args and options."""

        for a, b in [("only-extras", "extras"), ("no-root", "link"), ("only-extras", "link")]:
            if self.option(a) and self.option(b):
                self.line_error(f"error: conflicting options <opt>--{a}</opt> and <opt>--{b}</opt>", "error")
                return False

        return True

    def _get_projects_to_install(self) -> list[Project]:
        """Return the list of Slap projects to install."""

        from_path = self.option("from")
        return self.app.get_target_projects(self.option("only"), Path(from_path).resolve() if from_path else None)

    def _get_extras_to_install(self) -> set[str]:
        """Return a set of the extras that should be installed."""

        extras = set(map(str.strip, (self.option("extras") or self.option("only-extras") or "").split(",")))
        extras.discard("")

        if not self.option("no-dev") and not self.option("only-extras"):
            extras.add("dev")

        if not self.option("no-dev") and self.app.repository in self.config:
            # Add the dev extras from the repository configuration.
            extras.update(self.config[self.app.repository].dev_extras or [])

        return extras

    def _update_indexes_from_cli(self, indexes: Indexes) -> None:
        from slap.install.installer import IndexSpec

        for extra in (*self.option("extra-index"), *self.option("index")):
            spec = IndexSpec.parse(extra)
            if spec.name in indexes.urls:
                spec.url = spec.url or indexes.urls[spec.name]
            else:
                logger.warning('passed an --index option for a source that does not exist (source: "%s")', spec.name)
            indexes.urls[spec.name] = spec.url_with_auth

    def _link_projects(self, projects: list[Project]) -> None:
        from slap.ext.application.link import link_repository

        link_repository(self.io, projects, python=get_active_python_bin(self))

    # SymlinkHelper

    def get_dependencies_for_project(self, project: Path) -> list[Dependency]:
        # TODO (@NiklasRosenstein): Implement this method
        raise NotImplementedError

    def link_project(self, path: Path) -> None:
        project = self.app.repository.get_project_by_directory(path)
        self._link_projects([project])
