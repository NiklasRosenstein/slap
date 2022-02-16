
from pathlib import Path
from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin


class InfoCommandPlugin(Command, ApplicationPlugin):
  """ Show info about the Slam application workspace and the loaded projects. """

  name = "info"
  app: Application

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    for project in self.app.projects:
      if not project.is_python_project: continue
      packages = ", ".join(f"<opt>{p.name} ({p.root.relative_to(project.directory)})</opt>" for p in project.packages())
      self.line(f'Project <s>"{project.directory.relative_to(Path.cwd())}"</s>')
      self.line(f'  dist-name: <opt>{project.get_dist_name()}</opt>')
      self.line(f'  packages: {packages}')
      self.line(f'  readme: <opt>{project.handler().get_readme(project)}</opt>')
      self.line(f'  handler: <opt>{project.handler()}</opt>')
