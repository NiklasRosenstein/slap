
import os
import subprocess as sp
import typing as t

from nr.util.singleton import NotSet

from shut.application import Application, ApplicationPlugin, Command, IO, argument, option


class TestRunner:

  _colors = ['blue', 'cyan', 'magenta', 'yellow']
  _prev_color: t.ClassVar[str | None] = None

  def __init__(self, name: str, config: t.Any, io: IO, line_prefixing: bool = True) -> None:
    assert isinstance(config, str), type(config)
    self.name = name
    self.config = config
    self.io = io
    self.line_prefixing = line_prefixing

  def run(self) -> int:
    from cleo.io.io import OutputType  # type: ignore[import]
    from ptyprocess import PtyProcessUnicode  # type: ignore[import]

    color = self._colors[0]  if TestRunner._prev_color is None else self._colors[(self._colors.index(TestRunner._prev_color) + 1) % len(self._colors)]
    TestRunner._prev_color = color
    command = ['bash', '-c', self.config]

    try:
      cols, rows = os.get_terminal_size()
    except OSError:
      return sp.call(command)
    else:
      proc = PtyProcessUnicode.spawn(command, dimensions=(rows, cols))
      while not proc.eof():
        try:
          line = proc.readline().rstrip()
        except EOFError:
          break
        if self.line_prefixing:
          self.io.write(f'<fg={color}>{self.name}|</fg> ')
        self.io.write(line + '\n', type=OutputType.NORMAL)
      proc.wait()
      assert proc.exitstatus is not None
      return proc.exitstatus


class TestCommand(Command):
  """
  Execute the tests configured in <info>tool.shut.test</info>.

  <b>Example</b>

    <fg=cyan>[tool.shut.test]</fg>
    <fg=green>pytest</fg> = <fg=yellow>"pytest --cov=my_package tests/"</fg>
    <fg=green>mypy</fg> = <fg=yellow>"mypy src"</fg>
  """

  name = "test"
  description = "Execute all tests configured in <info>tool.shut.test</info>"
  arguments = [
    argument("test", "One or more tests to run (runs all if none are specified)", optional=True, multiple=True),
  ]
  options = [
    option("no-line-prefix", "s", "Do not prefix output from the test commands with the test name (default if "
      "a single argument for <info>test</info> is specified)."),
  ]
  options[0]._default = NotSet.Value  # Hack to set a default value for the flag

  def __init__(self, config: dict[str, str]) -> None:
    super().__init__()
    self.config = config

  def handle(self) -> int:
    if not self.config:
      self.line_error('error: no tests configured in <info>tool.shut.test</info>', 'error')
      return 1

    tests: list[str] | None = self.argument("test")
    if (no_line_prefix := self.option("no-line-prefix")) is NotSet.Value:
      no_line_prefix = (tests is not None and len(tests) == 1)

    tests = tests if tests else sorted(self.config.keys())
    if (unknown_tests := set(tests) - self.config.keys()):
      self.line_error(
        f'error: unknown test{"" if len(unknown_tests) == 1 else "s"} <b>{", ".join(unknown_tests)}</b>',
        'error'
      )
      return 1

    results = {}
    for test_name in tests:
      results[test_name] = TestRunner(test_name, self.config[test_name], self.io, not no_line_prefix).run()

    if len(tests) > 1:
      self.line('\n<comment>test summary:</comment>')
      for test_name, exit_code in results.items():
        color = 'green' if exit_code == 0 else 'red'
        self.line(f'  <fg={color}>•</fg> {test_name} (exit code: {exit_code})')

    return 0 if set(results.values()) == {0} else 1


class TestCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> dict[str, str]:
    return app.raw_config().get('test', {})

  def activate(self, app: Application, config: dict[str, str]) -> None:
    app.cleo.add(TestCommand(config))
