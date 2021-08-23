
import contextlib
import dataclasses
import logging
import os
import pkg_resources
import tempfile
import typing as t
import requests
from databind.core import annotations as A
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
      return pkg_resources.resource_string('shut', f'data/pylintrc_templates/{self.template}.ini').decode('utf8')
    except FileNotFoundError:
      raise ValueError(f'.pylintrc template {self.template!r} does not exist')


@dataclasses.dataclass
class PylintTestDriver(BaseTestDriver, Renderer['PackageModel']):
  """
  Runs Pylint.
  """

  NAME = 'pylint'

  #: Environment variables when calling PyLint.
  env: t.Dict[str, str] = dataclasses.field(default_factory=dict)

  #: Additional arguments when calling Pylint.
  args: t.List[str] = dataclasses.field(default_factory=list)

  #: Options for the .pylintrc file to use when invoking Pylint.
  rcfile: t.Optional[RcfileSettings] = None

  def test_package(self, package: 'PackageModel', runtime: Runtime, capture: bool) -> TestRun:
    source_dir = package.get_source_directory()
    metadata = package.get_python_package_metadata()
    path = metadata.package_directory if not metadata.is_single_module else metadata.filename
    command = runtime.python + ['-m', 'pylint', path] + self.args

    with contextlib.ExitStack() as stack:

      if self.rcfile and (self.rcfile.name or self.rcfile.render):
        local_rcfile = os.path.join(package.get_directory(), self.rcfile.name or RcfileSettings.DEFAULT_NAME)
        command += ['--rcfile', local_rcfile]

      elif self.rcfile and self.rcfile.template:
        fp = stack.enter_context(tempfile.NamedTemporaryFile(delete=False, mode='w'))
        stack.callback(lambda: os.unlink(fp.name))
        fp.write(self.rcfile.load_template())
        fp.close()
        command += ['--rcfile', fp.name]

      test_run = run_program_as_testcase(
        runtime.get_environment(), source_dir, 'pylint',
        command=command, env=self.env, cwd=source_dir, capture=capture)

    return test_run

  def get_test_requirements(self) -> t.List[Requirement]:
    return [Requirement('pylint')]

  def get_files(self, files: VirtualFiles, obj: 'PackageModel') -> None:
    if self.rcfile and self.rcfile.render and self.rcfile.template:
      def render_rcfile(fp: t.TextIO) -> None:
        assert self.rcfile
        fp.write(self.rcfile.load_template())
      files.add_dynamic(self.rcfile.name or RcfileSettings.DEFAULT_NAME, render_rcfile)
