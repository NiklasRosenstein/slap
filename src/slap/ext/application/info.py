
import os
from pathlib import Path
from slap.application import Application, Command, option
from slap.plugins import ApplicationPlugin


class InfoCommandPlugin(Command, ApplicationPlugin):
  """ Show info about the Slap application workspace and the loaded projects. """

  app: Application
  name = "info"

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    self.line(f'Repository <s>"{self.app.repository.directory}"</s>')
    self.line(f'  vcs: <opt>{self.app.repository.vcs()}</opt>')
    self.line(f'  host: <opt>{self.app.repository.host()}</opt>')
    self.line(f'  projects: <opt>{[p.id for p in self.app.repository.projects()]}</opt>')

    for project in self.app.repository.projects():
      if not project.is_python_project: continue
      packages_list = project.packages()
      packages = (
        '<i>none</i>'
        if packages_list is None
        else '[]' if len(packages_list or []) == 0
        else ", ".join(f"<opt>{p.name} ({os.path.relpath(p.root, project.directory)})</opt>" for p in packages_list))
      self.line(f'Project <s>"{os.path.relpath(project.directory, Path.cwd())}" (id: <opt>{project.id}</opt>)</s>')
      self.line(f'  version: <opt>{project.version()}</opt>')
      self.line(f'  dist-name: <opt>{project.dist_name()}</opt>')
      self.line(f'  packages: {packages}')
      self.line(f'  readme: <opt>{project.handler().get_readme(project)}</opt>')
      self.line(f'  handler: <opt>{project.handler()}</opt>')

      inter_deps = project.get_interdependencies(self.app.repository.projects())
      if inter_deps:
        projects = ", ".join(f"<opt>{p.dist_name()}</opt>" for p in inter_deps)
        self.line(f'  depends on: {projects}')

      deps = project.dependencies()
      self.line(f'  dependencies:')
      self._print_deps('run', deps.run)
      self._print_deps('dev', deps.dev)
      for key, value in deps.extra.items():
        self._print_deps(f'extra.{key}', value)

    return 0

  def _print_deps(self, prefix: str, deps: list[str]) -> None:
    if deps:
      self.line(f'    {prefix}:')
      for dep in sorted(deps, key=lambda s: s.lower()):
        self.line(f'      - <opt>{dep}</opt>')
    else:
      self.line(f'    {prefix}: <i>none</i>')
