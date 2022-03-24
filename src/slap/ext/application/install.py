
import dataclasses
import logging
import os
import shlex
import subprocess as sp
import typing as t
from pathlib import Path

from slap.application import Application, Command, option
from slap.configuration import Configuration
from slap.plugins import ApplicationPlugin
from slap.project import Project
from slap.util.python import Environment

from databind.core.settings import Alias, ExtraKeys


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


@dataclasses.dataclass
@ExtraKeys(True)
class InstallConfig:
  """ Separate install configuration under Slap that is entirely separate from the build system that is being used.
  This configures the behaviour of the `slap install` command. """

  #: Additional extras that are installable with `--extras` or `--only-extras`. These are taken into account
  #: for projects as well as the monorepository root. They may contain semantic version selector (same style
  #: as supported by Poetry).
  extras: dict[str, list[str]] = dataclasses.field(default_factory=dict)

  #: A list of extra names to install in addition to `dev` when using `slap install` (unless `--no-dev` is
  #: specified). If this option is not set, _all_ extras are installed.
  dev_extras: t.Annotated[list[str] | None, Alias('dev-extras')] = None


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
      description="Symlink the root project using <opt>slap link</opt> instead of installing it directly.",
    ),
    option(
      "no-dev",
      description="Do not install development dependencies.",
    ),
    option(
      "no-root",
      description="Do not install the package itself, but only its dependencies.",
    ),
    option(
      "extras",
      description="A comma-separated list of extras to install. Note that <s>\"dev\"</s> is a valid extras.",
      flag=False,
    ),
    option(
      "only-extras",
      description="Install only the specified extras. Note that <s>\"dev\"</s> is a valid extras.",
      flag=False,
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
    from databind.json import load
    self.config: dict[Configuration, InstallConfig] = {}
    for obj in app.configurations():
      self.config[obj] = load(obj.raw_config().get('install', {}), InstallConfig, filename=str(obj))
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    from slap.ext.project_handlers.poetry import convert_poetry_dependencies

    for a, b in [("only-extras", "extras"), ("no-root", "link"), ("only-extras", "link")]:
      if self.option(a) and self.option(b):
        self.line_error(f'error: conflicting options <opt>--{a}</opt> and <opt>--{b}</opt>', 'error')
        return 1

    if not venv_check(self):
      return 1

    if only_project := self.option("only"):
      project_path = Path(only_project).resolve()
      projects = [p for p in self.app.repository.projects() if p.directory.resolve() == project_path]
      if not projects:
        self.line_error(f'error: "{only_project}" does not point to a project', 'error')
        return 1
      assert len(projects) == 1, projects
      project_dependencies = self._get_project_dependencies(projects[0])
    else:
      projects = self.app.repository.projects()
      project_dependencies = []

    extras = {x.strip() for x in (self.option("extras") or self.option("only-extras") or '').split(',') if x.strip()}
    found_extras = {'dev'}

    if not self.option("no-dev") and self.app.repository in self.config:
      extras.update(self.config[self.app.repository].dev_extras or [])

    dependencies = []
    for project in projects + project_dependencies:
      if not project.is_python_project: continue
      if not self.option("no-root") and not self.option("link") and not self.option("only-extras") and project.packages():
        dependencies.append(str(project.directory.resolve()))
      elif not self.option("only-extras"):
        dependencies += project.dependencies().run
    for project in projects:
      if (not self.option("no-dev") and not self.option("only-extras")) or 'dev' in extras:
        dependencies += project.dependencies().dev

      # Determine the extras to install.
      config = self.config[project]
      project_extras = set(extras)
      if not self.option("no-dev"):
        if config.dev_extras is None:
          project_extras.update(project.dependencies().extra.keys())
          project_extras.update(config.extras.keys())
        else:
          project_extras.update(config.dev_extras)

      for extra in project_extras - {'dev'}:
        extra_deps = project.dependencies().extra.get(extra)
        if extra_deps is not None:
          found_extras.add(extra)
          dependencies += extra_deps

    # Look for extras also in the Slap specific install configuration.
    for obj, config in self.config.items():
      for extra in extras:
        dependencies += convert_poetry_dependencies(config.extras.get(extra, []))
        found_extras.add(extra)

    if missing_extras := extras - found_extras:
      self.line_error(f'error: extras that do not exist: <fg=yellow>{missing_extras}</fg>', 'error')
      return 1

    pip_command = [self.option("python"), "-m", "pip", "install"] + dependencies
    if self.option("quiet"):
      pip_command += ['-q']
    logger.info('Installing with Pip using command <subj>$ %s</subj>', ' '.join(map(shlex.quote, pip_command)))
    if (res := sp.call(pip_command)) != 0:
      return res

    if self.option("link"):
      self.call("link", ["--no-venv-check"] if self.option("no-venv-check") else [])

    return 0

  def _get_project_dependencies(self, project: Project) -> list[Project]:
    dependencies = project.get_interdependencies(self.app.repository.projects())
    for dep in dependencies[:]:
      dependencies = self._get_project_dependencies(dep) + dependencies
    return dependencies
