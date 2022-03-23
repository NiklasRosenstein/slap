
import datetime
import textwrap
from pathlib import Path

from slap import __version__
from slap.application import Application, Command, argument, option
from slap.plugins import ApplicationPlugin
from slap.util.external.licenses import get_license_metadata, wrap_license_text
from slap.util.vcs import get_git_author

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
      packages = [{{ include = "{path}", from = "src" }}]
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

      [tool.slap]
      typed = true

      [tool.slap.test]
      check = "slap check"
      mypy = "MYPYPATH=src mypy src/ --namespace-packages --explicit-package-bases"
      pytest = "pytest test/ -vv"

      [tool.mypy]
      pretty = true
      namespace_packages = true
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
    'src/{path}/__init__.py': '''

      __version__ = '0.1.0'
    ''',
    'test/test_import.py': '''
      def test_import():
        exec('from {dotted_name} import *')
    ''',
    'src/{path}/py.typed': '',
  }
}


class InitCommandPlugin(ApplicationPlugin, Command):
  """ Bootstrap some files for a Python project.

  Currently available templates:

  1. <info>poetry</info>
  """

  app: Application

  name = "init"
  arguments = [
    argument(
      "directory",
      description="The directory in which to create the generated files. If not specified, a new directory with "
        "the name specified via the <opt>--name</opt> option is created.",
      optional=True,
    )
  ]
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
      description="Render the content as Markdown (uses by the Slap docs)",
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
    author = get_git_author()
    directory = Path(self.argument("directory") or self.option("name").replace('.', '-'))

    scope = {
      'name': self.option("name"),
      'dotted_name': self.option("name").replace('-', '_'),
      'path': self.option("name").replace('.', '/').replace('-', '_'),
      'package': self.option("name").replace('.', '_').replace('-', '_'),
      'license': self.option("license"),
      'year': datetime.date.today().year,
      'author_name': author.name if author and author.name else 'Unknown',
      'author_email': author.email if author and author.email else 'me@unknown.org',
    }
    for filename, content in TEMPLATES[template].items():
      if filename == 'LICENSE':
        content = get_license_metadata(self.option("license")).license_text
        content = wrap_license_text(content)
        content = 'Copyright (c) {year} {author_name}\n\n'.format(**scope) + content
        content = f'The {self.option("license")} License\n\n' + content
      else:
        filename = filename.format(**scope)
        content = textwrap.dedent(content.format(**scope)).strip()
        if content:
          content += '\n'

      path = directory / filename

      if self.option("as-markdown"):
        print(f'```{path.suffix[1:]} title="{path}"')
        print(content, '    ')
        print(f'```\n\n')
        continue

      if path.exists() and not self.option("overwrite"):
        self.line(f'skip <info>{path}</info> (already exists)')
        continue

      if not self.option("dry") and not self.option("as-markdown"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

      self.line(f'write <info>{path}</info>')

    return 0
