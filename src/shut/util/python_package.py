
import dataclasses
from pathlib import Path
from setuptools import find_namespace_packages

from nr.util.algorithm.longest_common_substring import longest_common_substring


@dataclasses.dataclass
class Package:
  name: str
  path: Path


def detect_packages(directory: Path) -> list[Package]:
  """ Detects the Python packages in *directory*, making an effort to identify namespace packages correctly. """

  modules = find_namespace_packages(directory)
  if not modules:
    raise ValueError(f'no modules discovered in {directory}')

  if len(modules) > 1:
    def _filter(module: str) -> bool:
      return (directory / module.replace('.', '/') / '__init__.py').is_file()
    modules = list(filter(_filter, modules))

  if len(modules) > 1:
    # If we stil have multiple modules, we try to find the longest common path.
    common = longest_common_substring(*(x.split('.') for x in modules), start_only=True)
    if not common:
      raise ValueError(f'no common root package modules: {modules}')
    return '.'.join(common)

  return [Package(module, directory / Path(*module.split('/'))) for module in modules]