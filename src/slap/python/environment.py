
from __future__ import annotations

import dataclasses
import functools
import json
import pickle
import subprocess as sp
import textwrap
import typing as t
from pathlib import Path

from slap.python import pep508

if t.TYPE_CHECKING:
  import pkg_resources


@dataclasses.dataclass
class PythonEnvironment:
  """ Represents a Python environment. Provides functionality to introspect the environment. """

  executable: str
  version: str
  platform: str
  prefix: str
  base_prefix: str | None
  real_prefix: str | None
  pep508: pep508.Pep508Environment
  _has_pkg_resources: bool | None = None

  def is_venv(self) -> bool:
    """ Checks if the Python environment is a virtual environment. """

    return bool(self.real_prefix or (self.base_prefix and self.prefix != self.base_prefix))

  def has_pkg_resources(self) -> bool:
    """ Checks if the Python environment has the `pkg_resources` module available. """

    if self._has_pkg_resources is None:
      code = textwrap.dedent('''
        try: import pkg_resources
        except ImportError: print('false')
        else: print('true')
      ''')
      self._has_pkg_resources = json.loads(sp.check_output([self.executable, '-c', code]).decode())
    return self._has_pkg_resources

  @staticmethod
  @functools.lru_cache()
  def of(python: str | t.Sequence[str]) -> 'PythonEnvironment':
    """ Introspects the given Python installation to construct a #PythonEnvironment. """

    if isinstance(python, str):
      python = [python]

    # We ensure that the Pep508 module is importable.
    pep508_path = str(Path(pep508.__file__).parent)

    code = textwrap.dedent(f'''
      import sys, platform, json
      sys.path.append({pep508_path!r})
      import pep508
      try: import pkg_resources
      except ImportError: pkg_resources = None
      print(json.dumps({{
        "executable": sys.executable,
        "version": sys.version,
        "platform": platform.platform(),
        "prefix": sys.prefix,
        "base_prefix": getattr(sys, 'base_prefix', None),
        "real_prefix": getattr(sys, 'real_prefix', None),
        "pep508": pep508.Pep508Environment.current().as_json(),
        "_has_pkg_resources": pkg_resources is not None,
      }}))
    ''')

    payload = json.loads(sp.check_output(list(python) + ['-c', code]).decode())
    payload['pep508'] = pep508.Pep508Environment(**payload['pep508'])
    return PythonEnvironment(**payload)

  def get_distribution(self, distribution: str) -> pkg_resources.Distribution | None:
    """ Query the details for a single distribution in the Python environment. """

    return self.get_distributions([distribution])[distribution]

  def get_distributions(self, distributions: t.Collection[str]) -> dict[str, pkg_resources.Distribution | None]:
    """ Query the details for the given distributions in the Python environment with
    #pkg_resources.get_distribution(). """

    code = textwrap.dedent('''
      import sys, pkg_resources, pickle
      result = []
      for arg in sys.argv[1:]:
        try:
          dist = pkg_resources.get_distribution(arg)
        except pkg_resources.DistributionNotFound:
          dist = None
        result.append(dist  )
      sys.stdout.buffer.write(pickle.dumps(result))
    ''')

    keys = list(distributions)
    result = pickle.loads(sp.check_output([self.executable, '-c', code] + keys))
    return dict(zip(keys, result))


@dataclasses.dataclass
class DistributionMetadata:
  """ Additional metadata for a distribution. """

  license_name: str | None
  platform: str | None
  requires_python: str | None
  requirements: list[str]
  extras: set[str]


def get_distribution_metadata(dist: pkg_resources.Distribution) -> DistributionMetadata:
  """ Parses the distribution metadata. """

  from email.parser import Parser

  data = Parser().parsestr(dist.get_metadata(dist.PKG_INFO))

  return DistributionMetadata(
    license_name=data.get('License'),
    platform=data.get('Platform'),
    requires_python=data.get('Requires-Python'),
    requirements=data.get_all('Requires-Dist') or [],
    extras=set(data.get_all('Provides-Extra') or []),
  )
