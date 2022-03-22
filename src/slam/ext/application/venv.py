
import shutil
import string
import subprocess as sp
from pathlib import Path
from urllib import request

from slam.application import Application, Command, argument, option
from slam.plugins import ApplicationPlugin


class VenvCommand(Command):
  """ Create, activate and remove virtual environments.

  This command makes it easy to create and manage virtual environments, locally as well
  as globally. Local environments are stored in the `.venvs/` directory in the current
  directory. Global environments are stored in `~/.local/venvs`.

  In order to be able to use the <opt>-a,--activate</opt> option directly from this command,
  it must be shadowed by a function in your shell. Use the <opt>-i,--init-code</opt> command
  to get a code snippet that you can place in your shell's init scripts.
  """

  name = "venv"
  arguments = [
    argument(
      "name",
      description="The environment name.",
      optional=True,
    ),
  ]
  options = [
    option(
      "global", "g",
      description="Manage virtual environments in the global scope instead of the local directory."
    ),
    option(
      "activate", "a",
      description="Activate the environment given by the environment name. Note that using this option if used "
        "directly with the Slam CLI will cause an error because it needs to be shadowed by a function of your shell.",
    ),
    option(
      "create", "c",
      description="Create the environment with the given environment name.",
    ),
    option(
      "delete", "d",
      description="Delete the environment with the given environment name.",
    ),
    option(
      "list", "l",
      description="List the available environments.",
    ),
    option(
      "init-code", "i",
      description="Print the code snippet that can be placed in your shells init scripts to shadow this command "
        "in order to properly make use of the <opt>-a,--activate</opt> option.",
      flag=False,
    ),
    option(
      "python", "p",
      description="The Python executable to use to create the virtual environment. If this is not specified, "
        "it defaults to <code>python</code> + the environment name if the environment name looks like a version "
        "number (contains numbers and dots). Otehrwise, it defaults to <code>python3</code>.",
      flag=False,
    ),
    option(
      "called-from-shadow-func",
      description="Passed by the shell shadow function to inform the command that it was not invoked directly.",
    )
  ]

  def _validate_args(self) -> bool:
    for opt in ('activate', 'create', 'delete'):
      if self.option("init-code") and self.option(opt):
        self.line_error('error: <opt>-i,--init-code</opt> is not compatible with <opt>-{opt[0]},--{opt}</opt>', 'error')
        return False
      if self.option(opt) and not self.argument("name"):
        self.line_error('error: missing <opt>name</opt> argument', 'error')
        return False
    for opt in ('activate', 'create'):
      if self.option("delete") and self.option(opt):
        self.line_error('error: <opt>-d,--delete</opt> is not compatible with <opt>-{opt[0]},--{opt}</opt>', 'error')
        return False
    return True

  def _get_python_bin(self) -> str:
    python = self.option("python")
    name = self.argument("name")
    if not python and set(name).issubset(string.digits + '.'):
      python = f'python{name}'
    return python or 'python3'

  def _get_base_path(self) -> Path:
    if self.option("global"):
      return Path('~/.local/venvs').expanduser()
    else:
      return Path('.venvs')

  def _get_python_version(self, path: Path) -> None:
    return sp.check_output([path / 'bin' / 'python', '-c', 'import sys; print(" ".join(map(str.strip, sys.version.splitlines())))']).decode().strip()

  def _list_environments(self) -> None:
    base_path = self._get_base_path()
    paths = tuple(base_path.iterdir()) if base_path.exists() else ()
    if not paths:
      self.line_error(f'no environments in <s>"{base_path}"</s>', 'info')
      return
    self.line(f'{len(paths)} environment{"s" if len(paths) != 1 else ""} in <s>"{base_path}"</s>', 'info')
    for path in paths:
      self.line(f'• {path.name}\t\t<code>{self._get_python_version(path)}</code>')

  def _get_init_code(self, shell: str) -> str:
    if shell in ('bash', 'sh'):
      raise NotImplementedError
    else:
      self.line_error(f'error: init code for shell <s>{shell}</s> is not supported', 'error')
      return 1

  def handle(self) -> int:
    if not self._validate_args():
      return 1

    shell = self.option("init-code")
    if shell:
      self._get_init_code(shell)
      return 0

    if self.option("list"):
      self._list_environments()
      return 0

    python = self._get_python_bin()
    env_path = self._get_base_path() / self.argument("name")

    if self.option("create"):
      if env_path.exists():
        self.line_error(f'error: environment <s>"{env_path}"</s> already exists', 'error')
        return 1
      env_path.parent.mkdir(parents=True, exist_ok=True)
      sp.check_call([python, '-m', 'venv', env_path])

    if self.option("activate"):
      if not env_path.exists():
        self.line_error(f'error: environment <s>"{env_path}"</s> does not exist', 'error')
        return 1
      # TODO (@NiklasRosenstein): Adjust output based on the shell that this is called from?
      # TODO (@NiklasRosenstein): This also needs to be a different path on Windows.
      if not self.option("called-from-shadow-func"):
        self.line_error('warning: the <opt>-a,--activate</opt> option only works when shadowed by a shell function', 'warning')
      print(f'source "{env_path}/bin/activate"')

    if self.option("delete"):
      if not env_path.exists():
        self.line_error(f'error: environment <s>"{env_path}"</s> does not exist', 'error')
        return 1
      shutil.rmtree(env_path)


class VenvLinkCommand(Command):
  """ Link executables from a global virtual environment. """

  name = "venv link"


  def handle(self) -> int:
    print('venv link')
    return super().handle()


class VenvPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    app.cleo.add(VenvCommand())
    app.cleo.add(VenvLinkCommand())
