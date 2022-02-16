
from pathlib import Path
from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin


class InfoCommandPlugin(Command, ApplicationPlugin):
  """ Show info about the Slam application workspace and the loaded projects. """

  app: Application
  name = "info"

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    for project in self.app.projects:
      if not project.is_python_project: continue
      packages = ", ".join(f"<opt>{p.name} ({p.root.relative_to(project.directory)})</opt>" for p in project.packages())
      self.line(f'Project <s>"{project.directory.relative_to(Path.cwd())}" (id: <opt>{project.id}</opt>)</s>')
      self.line(f'  dist-name: <opt>{project.get_dist_name()}</opt>')
      self.line(f'  packages: {packages}')
      self.line(f'  readme: <opt>{project.handler().get_readme(project)}</opt>')
      self.line(f'  handler: <opt>{project.handler()}</opt>')

      deps = project.dependencies()
      self.line(f'  dependencies:')
      self._print_deps('run', deps.run)
      self._print_deps('dev', deps.dev)
      for key, value in deps.extra.items():
        self._print_deps(f'extra.{key}', value)

  def _print_deps(self, prefix: str, deps: list[str]) -> None:
      if deps:
        self.line(f'    {prefix}:')
        for dep in sorted(deps, key=lambda s: s.lower()):
          self.line(f'      - <opt>{dep}</opt>')
      else:
        self.line(f'    {prefix}: <i>none</i>')
