
import logging
import os
import typing as t
from pathlib import Path

from nr.util.singleton import NotSet

from slap.application import Application, Command, IO, argument, option
from slap.plugins import ApplicationPlugin
from slap.project import Project

logger = logging.getLogger(__name__)


class TestRunner:

  _colors = ['blue', 'cyan', 'magenta', 'yellow']
  _prev_color: t.ClassVar[str | None] = None

  def __init__(self, name: str, config: t.Any, io: IO, cwd: Path | None = None, line_prefixing: bool = True) -> None:
    assert isinstance(config, str), type(config)
    self.name = name
    self.config = config
    self.io = io
    self.cwd = cwd
    self.line_prefixing = line_prefixing

  def run(self) -> int:
    from codecs import getreader
    import subprocess as sp
    import sys
    from cleo.io.io import OutputType  # type: ignore[import]
    from ptyprocess import PtyProcessUnicode  # type: ignore[import]

    color = self._colors[0]  if TestRunner._prev_color is None else self._colors[(self._colors.index(TestRunner._prev_color) + 1) % len(self._colors)]
    TestRunner._prev_color = color
    command = ['bash', '-c', self.config]
    prefix = f'{self.name}| '

    logger.info('Running command <subj>%s</subj> in <val>%s</val>', command, self.cwd)

    try:
      cols, rows = os.get_terminal_size()
    except OSError:
      sproc = sp.Popen(command, cwd=self.cwd, stdout=sp.PIPE, stderr=sp.STDOUT)
      assert sproc.stdout
      stdout = getreader(sys.getdefaultencoding())(sproc.stdout)
      for line in iter(stdout.readline, ''):
        line = line.rstrip()
        if self.line_prefixing:
          self.io.write(f'<fg={color}>{prefix}</fg>')
        self.io.write(line + '\n', type=OutputType.NORMAL)
      sproc.wait()
      assert sproc.returncode is not None
      return sproc.returncode
    else:
      proc = PtyProcessUnicode.spawn(command, dimensions=(rows, cols - len(prefix)), cwd=self.cwd)
      while not proc.eof():
        try:
          line = proc.readline().rstrip()
        except EOFError:
          break
        if self.line_prefixing:
          self.io.write(f'<fg={color}>{prefix}</fg>')
        self.io.write(line + '\n', type=OutputType.NORMAL)
      proc.wait()
      assert proc.exitstatus is not None
      return proc.exitstatus


class Test(t.NamedTuple):
  project: Project
  name: str
  command: str

  @property
  def id(self) -> str:
    return f'{self.project.id}:{self.name}'


class TestCommandPlugin(Command, ApplicationPlugin):
  """
  Execute commands configured in <code>[tool.slap.test]</code>.

  <b>Example configuration:</b>

    <fg=cyan>[tool.slap.test]</fg>
    <fg=green>pytest</fg> = <fg=yellow>"pytest --cov=my_package tests/"</fg>
    <fg=green>mypy</fg> = <fg=yellow>"mypy src"</fg>

  <b>Example usage:</b>

    <fg=yellow>$</fg> slap test
    <fg=dark_gray>mypy | Success: no issues found in 12 source files
    pytest | ===================================== test session starts ======================================
    pytest | platform linux -- Python 3.10.2, pytest-6.2.5, py-1.11.0, pluggy-1.0.0
    ...</fg>
  """

  app: Application
  tests: list[Test]

  name = "test"
  arguments = [
    argument("test", "One or more tests to run (runs all if none are specified)", optional=True, multiple=True),
  ]
  options = [
    option(
      "no-line-prefix", "s",
      description="Do not prefix output from the test commands with the test name (default if a single argument "
        "for <info>test</info> is specified).",
    ),
    option(
      "list", "l",
      description="List all available tests",
    ),
  ]
  options[0]._default = NotSet.Value  # Hack to set a default value for the flag

  def load_configuration(self, app: Application) -> None:
    self.app = app
    self.tests = []
    for project in app.repository.projects():
      for test_name, command in project.raw_config().get('test', {}).items():
        self.tests.append(Test(project, test_name, command))

  def activate(self, app: Application, config: None) -> None:
    app.cleo.add(self)

  def _select_tests(self, name: str) -> set[Test]:
    result = set()
    for test in self.tests:
      use_test = (
        self.app.repository.is_monorepo and (
          name == test.id
          or (name.startswith(':') and test.name == name[1:])
          or (test.project.id == name)
        ) or
        not self.app.repository.is_monorepo and (
          name == test.name
        )
      )
      if use_test:
        result.add(test)
    if not result:
      raise ValueError(f'{name!r} did not match any tests')
    return result

  def handle(self) -> int:
    if self.option("list"):
      if self.argument("test"):
        self.line_error('error: incompatible arguments (<opt>test</opt> and <opt>-l,--list</opt>)', 'error')
        return 1
      for test in self.tests:
        print(test.id)
      return 0

    if not self.tests:
      self.line_error('error: no tests configured', 'error')
      return 1

    test_names: list[str] = self.argument("test")

    if not test_names:
      tests = set(self.tests)
    else:
      try:
        tests = {t for a in test_names for t in self._select_tests(a)}
      except ValueError as exc:
        self.line_error(f'error: {exc}', 'error')
        return 1

    if (no_line_prefix := self.option("no-line-prefix")) is NotSet.Value:
      no_line_prefix = (test_names is not None and len(tests) == 1)

    single_project = len(set(t.project for t in self.tests)) == 1

    results = {}
    for test in sorted(tests, key=lambda t: t.id):
      results[test.name if single_project else test.id] = TestRunner(
        test.name if single_project else test.id,
        test.command,
        self.io,
        test.project.directory,
        not no_line_prefix
      ).run()

    if len(tests) > 1:
      self.line('\n<comment>test summary:</comment>')
      for test_name, exit_code in results.items():
        color = 'green' if exit_code == 0 else 'red'
        self.line(f'  <fg={color}>•</fg> {test_name} (exit code: {exit_code})')

    return 0 if set(results.values()) == {0} else 1
