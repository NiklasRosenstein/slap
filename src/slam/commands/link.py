
import logging
import shutil
import textwrap
import typing as t
from pathlib  import Path

from flit.install import Installer  # type: ignore[import]
from nr.util.fs import atomic_swap

from slam.application import Application, ApplicationPlugin, Command, option


class LinkCommand(Command):
  """
  Symlink your Python package with the help of Flit.

  This command uses <u>Flit [0]</u> to symlink the Python package you are currently
  working on into your Python environment's site-packages. This is particulary
  useful if your project is using a <u>PEP 517 [1]</u> compatible build system that does
  not support editable installs.

  When you run this command, the <u>pyproject.toml</u> will be temporarily rewritten such
  that Flit can understand it. The following ways to describe a Python project are
  currently supported be the rewriter:

  1. <u>Poetry [2]</u>

    Supported configurations:
      - <fg=cyan>version</fg>
      - <fg=cyan>plugins</fg> (aka. "entrypoints")
      - <fg=cyan>scripts</fg>

  <b>Example usage:</b>

    <fg=yellow>$</fg> slam link
    <fg=dark_gray>Discovered modules in /projects/my_package/src: my_package
    Extras to install for deps 'all': {{'.none'}}
    Symlinking src/my_package -> .venv/lib/python3.10/site-packages/my_package</fg>

  <u>[0]: https://flit.readthedocs.io/en/latest/</u>
  <u>[1]: https://www.python.org/dev/peps/pep-0517/</u>
  <u>[2]: https://python-poetry.org/</u>
  """

  name = "link"
  help = textwrap.dedent(__doc__)
  options = [
    option(
      "python",
      description="The Python executable to link the package to.",
      flag=False,
      default="python",
    ),
    option(
      "dump-pyproject",
      description="Dump the updated pyproject.toml and do not actually do the linking.",
    )
  ]

  def __init__(self, app: Application):
    super().__init__()
    self.app = app

  def _load_pyproject(self) -> dict[str, t.Any]:
    return self.app.pyproject.value()

  def _save_pyproject(self, data: dict[str, t.Any]) -> None:
    self.app.pyproject.value(data)
    self.app.pyproject.save()

  def _get_source_directory(self) -> Path:
    directory = Path.cwd()
    if (src_dir := directory / 'src').is_dir():
      directory = src_dir
    return directory

  def _setup_flit_config(self, data: dict[str, t.Any]) -> bool:
    """ Internal. Makes sure the configuration in *data* is compatible with Flit. """

    poetry = data['tool'].get('poetry', {})
    plugins = poetry.get('plugins', {})
    scripts = poetry.get('scripts', {})
    project = data.setdefault('project', {})

    if plugins:
      project['entry-points'] = plugins
    if scripts:
      project['scripts'] = scripts

    # TODO (@NiklasRosenstein): Do we need to support gui-scripts as well?
    # TODO (@NiklasRosenstein): Support [tool.poetry.packages] which may contain multiple modules.

    src_directory = self._get_source_directory()
    module = self.app.get_packages()[0].name
    self.line(f'Discovered modules in {src_directory}: <fg=cyan>{module}</fg>')
    project['name'] = module
    project['version'] = poetry['version']
    project['description'] = ''

    return True

  def handle(self) -> int:
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    config = self._load_pyproject()
    if not self._setup_flit_config(config):
      return 1

    if self.option('dump-pyproject'):
      import tomli_w
      print(tomli_w.dumps(config))
      return 0

    with atomic_swap(self.app.pyproject.path, 'w', always_revert=True) as fp:
      fp.close()
      self._save_pyproject(config)
      installer = Installer.from_ini_path(
        self.app.pyproject.path, python=shutil.which(self.option("python")), symlink=True)
      installer.install()

    return 0


class LinkCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None):
    app.cleo.add(LinkCommand(app))
