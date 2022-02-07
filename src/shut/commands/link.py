
import logging
import shutil
import textwrap
import typing as t
from pathlib  import Path

from flit.install import Installer  # type: ignore[import]
from nr.util.algorithm import longest_common_substring
from nr.util.fs import atomic_swap
from setuptools import find_namespace_packages

from shut.application import Application, ApplicationPlugin, Command, option

PYPROJECT_TOML = Path('pyproject.toml')


def pick_modules_with_init_py(directory: Path, modules: list[str]) -> list[str]:
  def _filter(module: str) -> bool:
    return (directory / module.replace('.', '/') / '__init__.py').is_file()
  return list(filter(_filter, modules))


def identify_flit_module(directory: Path) -> str:
  """ Identifies the name of the module that is contained in *directory*. This uses #find_namespace_packages()
  and then tries to identify the one main module name that should be passed to the `tool.flit.metadata.module`
  option. """

  modules = find_namespace_packages(str(directory))
  if not modules:
    raise ValueError(f'no modules discovered in {directory}')

  if len(modules) > 1:
    modules = pick_modules_with_init_py(directory, modules)

  if len(modules) > 1:
    # If we stil have multiple modules, we try to find the longest common path.
    common = longest_common_substring(*(x.split('.') for x in modules), start_only=True)
    if not common:
      raise ValueError(f'no common root package modules: {modules}')
    return '.'.join(common)

  return modules[0]


class LinkCommand(Command):
  """
  Install your Python package in development mode.

  This command uses <u>Flit [0]</u> to symlink the Python package you are currently
  working on into your Python environment's site-packages. This is particulary
  useful if your project is using a <u>PEP 518 [1]</u> compatible build system that does
  not support editable installs.

  When you run this command, the <u>pyproject.toml</u> will be temporarily rewritten such
  that Flit can understand it. The following ways to describe a Python project are
  currently supported be the rewriter:

  1. <u>Poetry [2]</u>

    Supported configurations:
      - <fg=cyan>plugins</fg> (aka. "entrypoints")
      - <fg=cyan>scripts</fg>
      - <fg=cyan>packages</fg>

  <b>Example usage:</b>

    <fg=yellow>$</fg> shut link
    <fg=dark_gray>Discovered modules in /projects/my_package/src: my_package
    Extras to install for deps 'all': {{'.none'}}
    Symlinking src/my_package -> .venv/lib/python3.10/site-packages/my_package</fg>

  <u>[0]: https://flit.readthedocs.io/en/latest/</u>
  <u>[1]: https://www.python.org/dev/peps/pep-0518/</u>
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

  def _load_pyproject(self) -> dict[str, t.Any]:
    import tomli
    return tomli.loads(PYPROJECT_TOML.read_text())

  def _save_pyproject(self, data: dict[str, t.Any]) -> None:
    import tomli_w
    PYPROJECT_TOML.write_text(tomli_w.dumps(data))

  def _get_source_directory(self) -> Path:
    directory = Path.cwd()
    if (src_dir := directory / 'src').is_dir():
      directory = src_dir
    return directory

  def _setup_flit_config(self, data: dict[str, t.Any]) -> bool:
    """ Intenral. Makes sure the configuration in *data* is compatible with Flit. """

    poetry = data['tool'].get('poetry', {})
    plugins = poetry.get('plugins', {})
    scripts = poetry.get('scripts', {})
    project = data.setdefault('project', {})

    if plugins:
      project['entry-points'] = plugins
    if scripts:
      project['scripts'] = scripts

    # TODO (@NiklasRosenstein): Do we need to support gui-scripts as well?

    module = identify_flit_module(self._get_source_directory())
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

    with atomic_swap(PYPROJECT_TOML, 'w', always_revert=True) as fp:
      fp.close()
      self._save_pyproject(config)
      installer = Installer.from_ini_path(PYPROJECT_TOML, python=shutil.which(self.option("python")), symlink=True)
      installer.install()

    return 0


class LinkCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None):
    app.cleo.add(LinkCommand())
