from __future__ import annotations

import dataclasses
import logging
import os
import shlex
import typing as t
from pathlib import Path

from databind.core.settings import Alias, ExtraKeys

from slap.application import Application, Command, option
from slap.configuration import Configuration
from slap.ext.application.venv import VenvAwareCommand
from slap.plugins import ApplicationPlugin
from slap.project import Project

if t.TYPE_CHECKING:
    from slap.python.dependency import Dependency
    from slap.python.environment import PythonEnvironment


logger = logging.getLogger(__name__)
venv_check_option = option(
    "--no-venv-check",
    description="Do not check if the target Python environment is a virtual environment.",
)
python_option = option(
    "--python",
    "-p",
    description="The Python executable to install to.",
    flag=False,
)


def get_active_python_bin(cmd: Command) -> str:
    """Returns the active Python installation."""

    if hasattr(cmd, "_python_bin"):
        return cmd._python_bin  # type: ignore

    python = cmd.option("python")
    if not python:
        python = os.getenv("PYTHON")

    python = python or "python"
    cmd._python_bin = python
    return python


def venv_check(cmd: Command, message="refusing to install", env: PythonEnvironment | None = None) -> bool:
    from slap.python.environment import PythonEnvironment

    if not cmd.option("no-venv-check"):
        env = env or PythonEnvironment.of(get_active_python_bin(cmd))
        if not env.is_venv():
            cmd.line_error(f"error: {message} because you are not in a virtual environment", "error")
            cmd.line_error("       enter a virtual environment or use <opt>--no-venv-check</opt>", "error")
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
    options = [
        option(
            "--only",
            description="Path to the subproject to install only. May still cause other projects to be installed if "
            "required by the selected project via inter dependencies, but only their run dependencies will be installed.",
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
            flag=False,
        ),
        venv_check_option,
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

        from nr.util.stream import Stream

        from slap.install.installer import InstallOptions, PipInstaller, get_indexes_for_projects
        from slap.python.dependency import PathDependency, PypiDependency, parse_dependencies
        from slap.python.environment import PythonEnvironment

        if not self._validate_args():
            return 1

        python_environment = PythonEnvironment.of(get_active_python_bin(self))
        if not venv_check(self, env=python_environment):
            return False

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

        options = InstallOptions(
            indexes=get_indexes_for_projects(projects),
            quiet=self.option("quiet"),
            upgrade=self.option("upgrade"),
        )
        installer = PipInstaller(self)
        status_code = installer.install(dependencies, python_environment, options)
        if status_code != 0:
            return status_code

        if self.option("link"):
            self.link_project(Path("."))

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

        if only_project := self.option("only"):
            project_path = Path(only_project).resolve()
            projects = [p for p in self.app.repository.projects() if p.directory.resolve() == project_path]
            if not projects:
                self.line_error(f'error: "{only_project}" does not point to a project', "error")
                return []
            assert len(projects) == 1, projects
            return projects

        else:
            if not self.app.repository.projects:
                self.line_error(f"error: no projects found")
                return []
            return self.app.repository.get_projects_ordered()

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

    # SymlinkHelper

    def get_dependencies_for_project(self, project: Path) -> list[Dependency]:
        # TODO (@NiklasRosenstein): Implement this method
        raise NotImplementedError

    def link_project(self, project: Path) -> None:
        cwd = os.getcwd()
        os.chdir(project)
        command = ["--no-venv-check"] if self.option("no-venv-check") else []
        command += ["--python", get_active_python_bin(self)]
        self.call("link", " ".join(map(shlex.quote, command)))
        os.chdir(cwd)
