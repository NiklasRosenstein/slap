
import datetime
import textwrap
from pathlib import Path

from slam import __version__
from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin
from slam.util.external.licenses import get_license_metadata, wrap_license_text

TEMPLATES = {
  'poetry': {
    'pyproject.toml': '''
      [build-system]
      requires = ["poetry-core"]
      build-backend = "poetry.core.masonry.api"

      [tool.poetry]
      name = "{name}"
      version = "0.1.0"
      description = ""
      authors = ["{author_name} <{author_email}>"]
      license = "{license}"
      readme = "readme.md"
      packages = [{{ include="{package}", from="src" }}]
      classifiers = []
      keywords = []

      [tool.poetry.urls]
      # "Bug Tracker" = ""
      # Documentation = ""
      # Homepage = ""
      # Repository = ""

      [tool.poetry.dependencies]
      python = "^3.7"

      [tool.poetry.dev-dependencies]
      mypy = "*"
      pytest = "*"

      [tool.slam]
      typed = true

      [tool.slam.test]
      check = "slam check"
      mypy = "mypy src/ --namespace-packages"
      pytest = "pytest test/"

      [tool.mypy]
      pretty = true
      warn_redundant_casts = true
      warn_unused_ignores = true
      warn_no_return = true
      warn_unreachable = true
      show_error_context = true
      show_error_codes = true
    ''',
    'LICENSE': '',
    'readme.md': '''
      # {name}

    ''',
    '.gitignore': '''
      /.vscode
      /dist
      /build
      .venv/
      *.egg-info/
      __pycache__/
      poetry.lock
    ''',
    'src/{package}/__init__.py': '''

      __version__ = '0.1.0'
    ''',
    'src/{package}/py.typed': '',
  }
}


class InitCommandPlugin(ApplicationPlugin, Command):
  """ Bootstrap some files for a Python project.

  Currently available templates:

  1. <info>poetry</info>
  """

  app: Application

  name = "init"
  options = [
    option(
      "--name",
      description="The name of the Python package.",
      flag=False,
    ),
    option(
      "--license",
      description="The package license.",
      flag=False,
      default="MIT",
    ),
    option(
      "--template", "-t",
      description="The template to use.",
      flag=False,
      default="poetry",
    ),
    option(
      "--overwrite", "-f",
      description="Overwrite files.",
    ),
    option(
      "--dry", "-d",
      description="Dont actually write files.",
    ),
    option(
      "--as-markdown",
      description="Render the content as Markdown (uses by the Slam docs)",
    ),
  ]

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    if not self.option("name"):
      self.line_error('error: <opt>--name</opt> is required', 'error')
      return 1

    template = self.option("template")
    if template not in TEMPLATES:
      self.line_error(f'error: template "{template}" does not exist', 'error')
      return 1

    vcs = self.app.repository.vcs()
    author = vcs.get_author() if vcs else None

    scope = {
      'name': self.option("name"),
      'package': self.option("name").replace('.', '_').replace('-', '_'),
      'license': self.option("license"),
      'year': datetime.date.today().year,
      'author_name': author.name if author and author.name else 'Unknown',
      'author_email': author.email if author and author.email else 'me@unknown.org',
    }
    for filename, content in TEMPLATES[template].items():
      if filename == 'LICENSE':
        content = get_license_metadata(self.option("license"))
        content = wrap_license_text(content.license_text)
        content = 'Copyright (c) {year} {author_name}\n\n'.format(**scope) + content
        content = f'The {self.option("license")} License\n\n' + content
      else:
        filename = filename.format(**scope)
        content = textwrap.dedent(content.format(**scope)).strip()
        if content:
          content += '\n'
      if Path(filename).exists() and not self.option("overwrite"):
        self.line(f'skip <info>{filename}</info> (already exists)')
        continue
      Path(filename).parent.mkdir(parents=True, exist_ok=True)
      if not self.option("dry") and not self.option("as-markdown"):
        Path(filename).write_text(content)
      elif self.option("as-markdown"):
        print(f'=== "{filename}"\n')
        print(f'    ```{Path(filename).suffix[1:]}')
        print(textwrap.indent(content, '    '))
        print(f'    ```\n')
      self.line(f'write <info>{filename}</info>')

    return 0
