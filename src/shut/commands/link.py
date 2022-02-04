
import logging
import shutil
import textwrap
import typing as t
from pathlib  import Path

from flit.install import Installer  # type: ignore[import]
from nr.util.algorithm import longest_common_substring
from nr.util.fs import atomic_swap
from setuptools import find_namespace_packages  # type: ignore[import]

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

  modules = find_namespace_packages(directory)
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
  Poetry natively does not support editable installs (as of writing this on Jan 22, 2022). This
  command makes use of the <fg=green>Flit</fg> backend to leverage its excellent symlink support. Relevant parts of
  the Poetry configuration will by adpated such that no Flit related configuration needs to be added
  to <fg=cyan>pyproject.toml</fg>.

  <b>Example usage:</b>

    <fg=cyan>$ poetry link</fg>
    Discovered modules in /projects/poetry-link/src: my_package
    Extras to install for deps 'all': {{'.none'}}
    Symlinking src/my_package -> .venv/lib/python3.10/site-packages/my_package

  <b>How it works</b>

    First, the Poetry configuration in <fg=cyan>pyproject.toml</fg> will be updated temporarily to contain the
    relevant parts in the format that Flit understands. The changes to the configuration include

      • copy <fg=cyan>tool.poetry.plugins</fg> -> <b>tool.flit.entrypoints</b>
      • copy <fg=cyan>tool.poetry.scripts</fg> -> <b>tool.flit.scripts</b>
      • add <b>project</b>
        • the <b>module</b> is derived automatically using <fg=cyan>setuptools.find_namespace_packages()</fg> on the
          <b>src/</b> directory, if it exists, or otherwise on the current directory. Note that Flit
          only supports installing one package at a time, so it will be an error if setuptools
          discovers more than one package.

    Then, while the configuration is in an updated state, <fg=cyan>$ flit install -s --python `which python`</fg> is
    invoked. This will symlink your package into your currently active Python environment. (Note that right
    now, the plugin does not support auto-detecting the virtual environment automatically created for you by
    Poetry and the environment in which you want to symlink the package to needs to be active).

    Finally, the configuration is reverted to its original state.

  <info>This command is available because you have the <b>poetry-link</b> package installed.</info>
  """

  name = "link"
  description = "Install your package in development mode using Flit."
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

  def load_configuration(self) -> None:
    return None

  def activate(self, app: Application, config: None):
    app.cleo.add(LinkCommand())
