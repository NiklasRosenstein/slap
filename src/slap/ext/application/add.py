
import logging
import shlex
import subprocess as sp

from slap.application import Application, Command, argument, option
from slap.plugins import ApplicationPlugin
from slap.ext.application.install import python_option, venv_check, venv_check_option
from slap.python.dependency import PypiDependency, VersionSpec

logger = logging.getLogger(__name__)


class AddCommandPlugin(Command, ApplicationPlugin):
  """ Add one or more dependencies to a project. """

  app: Application
  name = "add"

  arguments = [
    argument(
      "packages",
      description="One or more packages to install with Pip and add to the project configuration.",
      multiple=True,
    )
  ]
  options = [
    option(
      "--dev", "-d",
      description="Add as development dependencies.",
    ),
    option(
      "--extra", "-e",
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
      "--source"
    ),
    venv_check_option,
    python_option,
  ]

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    from nr.util.stream import Stream
    from slap.install.installer import PipInstaller
    from slap.python.environment import PythonEnvironment

    if not self._validate_options():
      return 1

    project = self.app.main_project()
    if not project or not project.is_python_project:
      self.line_error(f'error: not situated in a Python project', 'error')
      return 1

    dependencies: dict[str, PypiDependency] = {}
    for package in self.argument("packages"):
      dependency = PypiDependency.parse(package)
      if dependency.name in dependencies:
        self.line_error(f'error: package specified more than once: <b>{dependency.name}</b>', 'error')
        return 1
      dependencies[dependency.name] = dependency

    python = PythonEnvironment.of(self.option("python"))
    distributions = python.get_distributions(dependencies.keys())
    where = 'dev' if self.option("dev") else (self.option("extra") or "run")

    to_install = (
      Stream(dependencies.values())
      .filter(lambda d: distributions[d.name] is None)
      .flatmap(PipInstaller.dependency_to_pip_arguments)
      .collect()
    )

    if to_install:
      self.line('Installing ' + ' '.join(f'<fg=cyan>{p}</fg>' for p in to_install))
      pip_install = [python.executable, "-m", "pip"] + ["install", "-q"] + to_install
      logger.info('Running <subj>$ %s</subj>', ' '.join(map(shlex.quote, pip_install)))
      sp.check_call(pip_install)

    distributions.update(python.get_distributions({k for k in distributions if distributions[k] is None}))
    for dep_name, dependency in dependencies.items():
      dist = distributions[dep_name]
      if not dist:
        self.line_error(
          f'error: unable to find distribution <fg=cyan>{dep_name!r}</fg> in <s>{python.executable}</s>',
          'error'
        )
        return 1
      if not dependency.version:
        dependency.version = VersionSpec('^' + dist.version)
      self.line(f'Adding <fg=cyan>{dependency}</fg>')
      project.add_dependency(dependency.name, dependency.version, where)

    return 0

  def _validate_options(self) -> bool:
    if not self.option("no-install") and not venv_check(self):
      return False
    if self.option("dev") and self.option("extra"):
      self.line_error('error: cannot combine --dev and --extra', 'error')
      return False
    return True
