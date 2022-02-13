
import dataclasses
from pathlib import Path
from setuptools import find_namespace_packages

from nr.util.algorithm.longest_common_substring import longest_common_substring

IGNORED_MODULES = ['test', 'tests', 'docs']


@dataclasses.dataclass
class Package:
  name: str   #: The name of the package. Contains periods in case of a namespace package.
  path: Path  #: The path to the package directory. This points to the namespace package if applicable.
  root: Path  #: The root directory that contains the package.


def detect_packages(directory: Path) -> list[Package]:
  """ Detects the Python packages in *directory*, making an effort to identify namespace packages correctly. """

  assert isinstance(directory, Path)
  modules = find_namespace_packages(str(directory))
  if not modules:
    raise ValueError(f'no modules discovered in {directory}')

  if len(modules) > 1:
    def _filter(module: str) -> bool:
      return (directory / module.replace('.', '/') / '__init__.py').is_file()
    modules = list(filter(_filter, modules))

  if len(modules) > 1:
    modules = [
      m for m in modules
      if m not in IGNORED_MODULES and
        ('.' not in m or m.split('.')[0] not in IGNORED_MODULES)
    ]

  if len(modules) > 1:
    # If we stil have multiple modules, we try to find the longest common path.
    common = longest_common_substring(*(x.split('.') for x in modules), start_only=True)
    if not common:
      raise ValueError(f'no common root package modules: {modules}')
    modules = ['.'.join(common)]

  return [Package(module, directory / Path(*module.split('/')), directory) for module in modules]
