
import logging
import os
import shlex
from pathlib import Path
import subprocess as sp

from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin
from slam.project import Project
from slam.util.python import Environment

logger = logging.getLogger(__name__)
venv_check_option = option(
  "--no-venv-check",
  description="Do not check if the target Python environment is a virtual environment.",
)


def venv_check(cmd: Command, message='refusing to install') -> bool:
  if not cmd.option("no-venv-check"):
    env = Environment.of(cmd.option("python"))
    if not env.is_venv():
      cmd.line_error(f'error: {message} because you are not in a virtual environment', 'error')
      cmd.line_error('       enter a virtual environment or use <opt>--no-venv-check</opt>', 'error')
      return False
  return True


class InstallCommandPlugin(Command, ApplicationPlugin):
  """ Install your project and its dependencies via Pip. """

  app: Application
  name = "install"
  options = [
    option(
      "only",
      description="Path to the subproject to install only. May still cause other projects to be installed if "
        "required by the selected project via inter dependencies, but only their run dependencies will be installed.",
      flag=False,
    ),
    option(
      "link",
      description="Symlink the root project using <opt>slam link</opt> instead of installing it directly.",
    ),
    option(
      "no-dev",
      description="Do not install development dependencies.",
    ),
    option(
      "no-root",
      description="Do not install the package itself, but only its dependencies.",
    ),
    venv_check_option,
    option(
      "python", "p",
      description="The Python executable to install to.",
      flag=False,
      default=os.getenv('PYTHON', 'python'),
    ),
  ]

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    if not venv_check(self):
      return 1

    if only_project := self.option("only"):
      project_path = Path(only_project).resolve()
      projects = [p for p in self.app.projects if p.directory.resolve() == project_path]
      if not projects:
        self.line_error(f'error: "{only_project}" does not point to a project', 'error')
        return 1
      assert len(projects) == 1, projects
      project_dependencies = self._get_project_dependencies(projects[0])
    else:
      projects = self.app.get_projects_in_topological_order()
      project_dependencies = []

    dependencies = []
    for project in projects + project_dependencies:
      if not project.is_python_project: continue
      if not self.option("no-root") and not self.option("link"):
        dependencies.append(str(project.directory.resolve()))
      else:
        dependencies += project.dependencies().run
    for project in projects:
      if not self.option("no-dev"):
        dependencies += project.dependencies().dev

    pip_command = [self.option("python"), "-m", "pip", "install"] + dependencies
    if self.option("quiet"):
      pip_command += ['-q']
    logger.info('Installing with Pip using command <subj>$ %s</subj>', ' '.join(map(shlex.quote, pip_command)))
    if (res := sp.call(pip_command)) != 0:
      return res

    if self.option("link"):
      self.call("link")

    return 0

  def _get_project_dependencies(self, project: Project) -> list[Project]:
    dependencies = project.get_interdependencies(self.app.projects)
    for dep in dependencies[:]:
      dependencies = self._get_project_dependencies(dep) + dependencies
    return dependencies
