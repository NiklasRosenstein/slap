
import contextlib
import dataclasses
import logging
import os
import pkg_resources
import tempfile
import typing as t
import requests
from databind.core import annotations as A
from shut.data import load_string
from shut.model.requirements import Requirement
from shut.renderers.core import Renderer
from shut.test.base import BaseTestDriver, Runtime, TestRun, run_program_as_testcase
from shut.utils.io.virtual import VirtualFiles

if t.TYPE_CHECKING:
  from shut.model.package import PackageModel

log = logging.getLogger(__name__)


@dataclasses.dataclass
class RcfileSettings:

  DEFAULT_NAME = '.pylintrc'

  #: A template to use for the `.pylintrc` file. Must either be the name of a template delivered
  #: with shut (currently this is only `"shut"`) or a URL.
  template: t.Optional[str] = None

  #: If enabled, the rcfile will be rendered into the project directory on `shut pkg update`.
  render: bool = False

  #: The name under which to render the rcfile.
  name: t.Optional[str] = None

  # TODO (@NiklasRosenstein): Support overrides in the rcfile template.

  def __post_init__(self) -> None:
    if self.render and not self.template:
      raise ValueError(f'RcfileSettings.template must be set if RcfileSettings.render is enabled')

  def load_template(self) -> str:
    if not self.template:
      raise ValueError(f'RcfileSettings.template is not set')
    if self.template.startswith('http://') or self.template.startswith('https://'):
      response = requests.get(self.template)
      response.raise_for_status()
      return response.text
    try:
      return load_string(f'pylintrc_templates/{self.template}.ini')
    except FileNotFoundError:
      raise ValueError(f'.pylintrc template {self.template!r} does not exist')


@dataclasses.dataclass
class PylintTestDriver(BaseTestDriver):
  """
  Runs Pylint.
  """

  NAME = 'pylint'

  #: Environment variables when calling PyLint.
  env: t.Dict[str, str] = dataclasses.field(default_factory=dict)

  #: Additional arguments when calling Pylint.
  args: t.List[str] = dataclasses.field(default_factory=list)

  #: The pylint RC file to use. If not specified, not explicit rcfile is passed to the pylint CLI.
  rcfile: t.Optional[str] = None

  def test_package(self, package: 'PackageModel', runtime: Runtime, capture: bool) -> TestRun:
    directory = package.get_directory()
    metadata = package.get_python_package_metadata()
    path = metadata.package_directory if not metadata.is_single_module else metadata.filename
    command = runtime.python + ['-m', 'pylint', os.path.relpath(path, directory)] + self.args

    if self.rcfile:
      command += ['--rcfile', self.rcfile]

    test_run = run_program_as_testcase(
      environment=runtime.get_environment(),
      filename=package.get_source_directory(),
      test_run_name='pylint',
      command=command,
      env=self.env,
      cwd=package.get_directory(),
      capture=capture)

    return test_run

  def get_test_requirements(self) -> t.List[Requirement]:
    return [Requirement('pylint')]
