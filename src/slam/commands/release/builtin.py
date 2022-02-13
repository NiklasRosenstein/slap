
import dataclasses
from pathlib import Path

from slam.application import IO
from slam.util.python_package import Package
from .api import ReleasePlugin, VersionRef, match_version_ref_pattern
from .config import VersionRefConfig


@dataclasses.dataclass
class VersionRefConfigMatcherPlugin(ReleasePlugin):
  """ This plugin matches a list of #VersionRefConfig definitions and returns the matched version references. This
  plugin is used to match the `tool.slam.release.references` config option and is always used. It should not be
  registered in the `slam.plugins.release` entrypoint group.
  """

  PYPROJECT_TOML_PATTERN = r'^version\s*=\s*[\'"]?(.*?)[\'"]'

  pyproject_toml: Path
  references: list[VersionRefConfig]

  def get_version_refs(self, io: 'IO') -> list[VersionRef]:
    results = []
    references = self.references[:]
    if self.pyproject_toml.exists():
      references.insert(0, VersionRefConfig(str(self.pyproject_toml), self.PYPROJECT_TOML_PATTERN))
    for config in references:
      pattern = config.pattern.replace('{version}', r'(.*?)')
      version_ref = match_version_ref_pattern(Path(config.file), pattern)
      if version_ref is not None:
        results.append(version_ref)
    return results


@dataclasses.dataclass
class SourceCodeVersionMatcherPlugin(ReleasePlugin):
  """ This plugin searches for a `__version__` key in the source code of the project and return it as a version
  reference. Based on the Poetry configuration (considering `tool.poetry.packages` and searching in the `src/`
  folder if it exists), the following source files will be checked:

  * `__init__.py`
  * `__about__.py`
  * `_version.py`

  Note that configuring `tool.poetry.packages` is needed for the detection to work correctly with PEP420
  namespace packages.
  """

  VERSION_REGEX = r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]'
  FILENAMES = ['__init__.py', '__about__.py', '_version.py']

  packages: list[Package]

  def get_version_refs(self, io: 'IO') -> list[VersionRef]:
    if not self.packages:
      return []
    results = []
    for package in self.packages:
      for filename in self.FILENAMES:
        path = package.path / filename
        if path.exists():
          version_ref = match_version_ref_pattern(path, self.VERSION_REGEX)
          if version_ref:
            results.append(version_ref)
            break
    if not results:
      message = '<fg=yellow>warning: unable to detect <b>__version__</b> in a source file'
      io.write_error_line(message + '</fg>')
    return results
