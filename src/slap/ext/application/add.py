
import logging
import shlex
import subprocess as sp

from slap.application import Application, Command, argument, option
from slap.plugins import ApplicationPlugin
from slap.ext.application.install import python_option, venv_check, venv_check_option
from slap.util.python import Environment
from slap.util.semver import parse_dependency

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
    venv_check_option,
    python_option,
  ]

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    from poetry.core.packages.dependency import Dependency  # type: ignore[import]

    if not self._validate_options():
      return 1

    project = self.app.main_project()
    if not project or not project.is_python_project:
      self.line_error(f'error: not situated in a Python project', 'error')
      return 1

    dependencies: dict[str, Dependency] = {}
    for package in self.argument("packages"):
      dep = parse_dependency(package)
      if dep.name in dependencies:
        self.line_error(f'error: package specified more than once: <b>{dep.name}</b>', 'error')
        return 1
      dependencies[dep.name] = dep

    python = Environment.of(self.option("python"))
    distributions = python.get_distributions(dependencies.keys())
    where = 'dev' if self.option("dev") else (self.option("extra") or "run")

    to_install = [d.to_pep_508() for d in dependencies.values() if distributions[d.name] is None]
    if to_install:
      self.line('Installing ' + ' '.join(f'<fg=cyan>{p}</fg>' for p in to_install))
      pip_install = [python.executable, "-m", "pip"] + ["install", "-q"] + to_install
      logger.info('Running <subj>$ %s</subj>', ' '.join(map(shlex.quote, pip_install)))
      sp.check_call(pip_install)

    distributions.update(python.get_distributions({k for k in distributions if distributions[k] is None}))
    for package_name, dep in dependencies.items():
      if package_name == dep.name:
        dist = distributions[dep.name]
        if not dist:
          self.line_error(
            f'error: unable to find distribution <fg=cyan>{package_name!r}</fg> in <s>{python.executable}</s>',
            'error'
          )
          return 1
        dep = Dependency(package_name, '^' + dist.version)
      self.line(f'Adding <fg=cyan>{dep.name} {dep.pretty_constraint}</fg>')
      project.add_dependency(dep, where)

    return 0

  def _validate_options(self) -> bool:
    if not self.option("no-install") and not venv_check(self):
      return False
    if self.option("dev") and self.option("extra"):
      self.line_error('error: cannot combine --dev and --extra', 'error')
      return False
    return True
