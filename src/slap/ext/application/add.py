import logging

from slap.application import Application, argument, option
from slap.ext.application.install import get_active_python_bin, python_option, venv_check
from slap.ext.application.venv import VenvAwareCommand
from slap.plugins import ApplicationPlugin
from slap.python.dependency import PypiDependency, VersionSpec

logger = logging.getLogger(__name__)


class AddCommandPlugin(VenvAwareCommand, ApplicationPlugin):
    """Add one or more dependencies to a project."""

    app: Application
    name = "add"

    arguments = [
        argument(
            "packages",
            description="One or more packages to install with Pip and add to the project configuration.",
            multiple=True,
        )
    ]
    options = VenvAwareCommand.options + [
        option(
            "--dev",
            "-d",
            description="Add as development dependencies.",
        ),
        option(
            "--extra",
            "-e",
            description="Add as extra dependencies for the specified extra name.",
            flag=False,
        ),
        option(
            "--no-install",
            description="Do not actually install the dependencies with Pip. Note that if the dependency is not already "
            "installed and no version selector is specified with the package name, it will fall back to a match-all "
            "version range (`*`).",
        ),
        option(
            "--source",
            description="Specify the source from which the package should be installed.",
            flag=False,
        ),
        option(
            "--upgrade",
            description="Upgrade dependencies that are already installed and declared in the project. If the "
            "dependency is already declared, the --source option can be skipped as it will be inherited from "
            "the declaration.",
        ),
        python_option,
    ]

    def load_configuration(self, app: Application) -> None:
        return None

    def activate(self, app: Application, config: None) -> None:
        self.app = app
        app.cleo.add(self)

    def handle(self) -> int:
        from nr.stream import Stream

        from slap.install.installer import InstallOptions, PipInstaller, get_indexes_for_projects
        from slap.python.environment import PythonEnvironment

        if not self._validate_options():
            return 1

        result = super().handle()
        if result != 0:
            return result

        project = self.app.main_project()
        if not project or not project.is_python_project:
            self.line_error("error: not situated in a Python project", "error")
            return 1

        dependencies: dict[str, PypiDependency] = {}
        for package in self.argument("packages"):
            dependency = PypiDependency.parse(package)
            if dependency.name in dependencies:
                self.line_error(f"error: package specified more than once: <b>{dependency.name}</b>", "error")
                return 1
            dependency.source = self.option("source")
            dependencies[dependency.name] = dependency

        python = PythonEnvironment.of(get_active_python_bin(self))
        distributions = python.get_distributions(dependencies.keys())
        where = "dev" if self.option("dev") else (self.option("extra") or "run")

        to_install = (
            Stream(dependencies.values())
            .map(lambda dep: (dep, distributions[dep.name]))
            .filter(
                lambda item: self.option("upgrade") or item[1] is None or not item[0].version.accepts(item[1].version)
            )
            .map(lambda item: item[0])
            .collect()
        )

        if to_install:
            indexes = get_indexes_for_projects([project])
            config = InstallOptions(indexes, True, self.option("upgrade"))
            installer = PipInstaller(symlink_helper=None)

            self.line("Installing " + " ".join(f"<fg=cyan>{p}</fg>" for p in to_install))

            status_code = installer.install(to_install, python, config)
            if status_code != 0:
                return status_code

        distributions.update(python.get_distributions({k for k in distributions if distributions[k] is None}))
        for dep_name, dependency in dependencies.items():
            dist = distributions[dep_name]
            if not dist:
                self.line_error(
                    f"error: unable to find distribution <fg=cyan>{dep_name!r}</fg> in <s>{python.executable}</s>",
                    "error",
                )
                return 1
            if not dependency.version:
                dependency.version = VersionSpec("^" + dist.version)
            self.line(f"Adding <fg=cyan>{dependency}</fg>")
            project.add_dependency(dependency, where)

        return 0

    def _validate_options(self) -> bool:
        if not self.option("no-install") and not venv_check(self):
            return False
        if self.option("no-install") and self.option("upgrade"):
            self.line_error("error: cannot --no-install and --upgrade", "error")
            return False
        if self.option("dev") and self.option("extra"):
            self.line_error("error: cannot combine --dev and --extra", "error")
            return False
        return True
