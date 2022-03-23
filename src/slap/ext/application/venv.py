
import os
import shutil
import string
import subprocess as sp
import typing as t
from pathlib import Path

from slap.application import Application, Command, argument, option
from slap.plugins import ApplicationPlugin

GLOBAL_BIN_DIRECTORY = Path('~/.local/bin').expanduser()
GLOBAL_VENVS_DIRECTORY = Path('~/.local/venvs').expanduser()\

SHADOW_INIT_SCRIPTS = {
  'bash': '''
    function slap() {
      local ORIGINAL=$(which slap)
      if ! [ $? = 0 ]; then
        >&2 echo "error: command 'slap' does not exist"
        return 127
      fi
      if [ "$1" == "venv" ] && [[ "$2" =~ -[gc]*a[gc]* ]]; then
        eval "$(SLAP_SHADOW=true "$ORIGINAL" "$@")"
      else
        "$ORIGINAL" "$@"
      fi
      return $?
    }
  ''',
}

USER_INIT_SCRIPTS = {
  'bash': 'which slap >/dev/null && eval "$(SLAP_SHADOW=true slap venv -i bash)"',
}


class Venv:

  def __init__(self, directory: Path) -> None:
    self.directory = directory

  @property
  def name(self) -> str:
    return self.directory.name

  def exists(self) -> bool:
    return self.directory.exists()

  def create(self, python_bin: str) -> None:
    self.directory.parent.mkdir(parents=True, exist_ok=True)
    sp.check_call([python_bin, '-m', 'venv', self.directory])

  def delete(self) -> None:
    shutil.rmtree(self.directory)

  def get_bin_directory(self) -> Path:
    if os.name == 'nt':
      return self.directory / 'Scripts'
    else:
      return self.directory / 'bin'

  def get_bin(self, program: str) -> Path:
    path = self.get_bin_directory() / program
    if os.name == 'nt':
      path = path.with_name(path.name + '.exe')
    return path

  def get_python_version(self) -> str:
    return sp.check_output([self.get_bin('python'), '-c', 'import sys; print(sys.version)']).decode().strip()


class VenvManager:

  def __init__(self, directory: Path | None = None) -> None:
    self.directory = directory or Path('.venvs')

  def ls(self) -> t.Iterable[Venv]:
    if not self.directory.exists():
      return
    for path in self.directory.iterdir():
      yield Venv(path)

  def get(self, venv_name: str) -> Venv:
    return Venv(self.directory / venv_name)



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
        "directly with the Slap CLI will cause an error because it needs to be shadowed by a function of your shell.",
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
        "in order to properly make use of the <opt>-a,--activate</opt> option. Currently supported shells are: "
        + ", ".join(USER_INIT_SCRIPTS),
      flag=False,
    ),
    option(
      "python", "p",
      description="The Python executable to use to create the virtual environment. If this is not specified, "
        "it defaults to <code>python</code> + the environment name if the environment name looks like a version "
        "number (contains numbers and dots). Otehrwise, it defaults to <code>python3</code>.",
      flag=False,
    )
  ]

  def _validate_args(self) -> bool:
    for opt in ('activate', 'create', 'delete'):
      if self.option("init-code") and self.option(opt):
        self.line_error(f'error: <opt>-i,--init-code</opt> is not compatible with <opt>-{opt[0]},--{opt}</opt>', 'error')
        return False
      if self.option("list") and self.option(opt):
        self.line_error(f'error: <opt>-l,--list</opt> is not compatible with <opt>-{opt[0]},--{opt}</opt>', 'error')
        return False
      if self.option(opt) and not self.argument("name"):
        self.line_error('error: missing <opt>name</opt> argument', 'error')
        return False
    for opt in ('activate', 'create'):
      if self.option("delete") and self.option(opt):
        self.line_error('error: <opt>-d,--delete</opt> is not compatible with <opt>-{opt[0]},--{opt}</opt>', 'error')
        return False
    if not any(self.option(opt) for opt in ('activate', 'create', 'delete', 'init-code', 'list')):
      self.line_error('error: no options supplied', 'error')
      return False
    return True

  def _get_python_bin(self) -> str:
    python = self.option("python")
    name = self.argument("name")
    if not python and set(name).issubset(string.digits + '.'):
      python = f'python{name}'
    return python or 'python3'

  def _list_environments(self, manager: VenvManager) -> None:
    venvs = list(manager.ls())
    if not venvs:
      self.line_error(f'no environments in <s>"{manager.directory}"</s>', 'info')
      return
    self.line(f'{len(venvs)} environment{"s" if len(venvs) != 1 else ""} in <s>"{manager.directory}"</s>', 'info')
    maxw = max(len(venv.name) for venv in venvs)
    for venv in venvs:
      self.line(f'• {venv.name.ljust(maxw)}  <code>{venv.get_python_version().splitlines()[0]}</code>')

  def _is_called_from_shadow(self) -> bool:
    return os.getenv('SLAP_SHADOW') == 'true'

  def _get_init_code(self, shell: str) -> int:
    import textwrap
    source = SHADOW_INIT_SCRIPTS if self._is_called_from_shadow() else USER_INIT_SCRIPTS
    if shell in source:
      print(textwrap.dedent(source[shell]))
      return 0
    else:
      self.line_error(f'error: init code for shell <s>{shell}</s> is not supported', 'error')
      return 1

  def handle(self) -> int:
    if not self._validate_args():
      return 1

    shell = self.option("init-code")
    if shell:
      return self._get_init_code(shell)

    manager = VenvManager(GLOBAL_VENVS_DIRECTORY if self.option("global") else Path(".venvs"))

    if self.option("list"):
      self._list_environments(manager)
      return 0

    python = self._get_python_bin()
    venv = manager.get(self.argument("name"))

    if self.option("create"):
      if venv.exists():
        self.line_error(f'error: environment <s>"{venv.name}"</s> already exists', 'error')
        return 1
      self.line_error(f'creating environment <s>"{venv.name}"</s> (using <code>{python}</code>)', 'info')
      venv.create(python)

    if self.option("activate"):
      if not venv.exists():
        self.line_error(f'error: environment <s>"{venv.name}"</s> does not exist', 'error')
        return 1
      # TODO (@NiklasRosenstein): Adjust output based on the shell that this is called from?
      # TODO (@NiklasRosenstein): This also needs to be a different path on Windows.
      if not self._is_called_from_shadow():
        self.line_error('warning: the <opt>-a,--activate</opt> option only works when shadowed by a shell function', 'warning')
      print(f'source "{venv.get_bin("activate")}"')

    if self.option("delete"):
      if not venv.exists():
        self.line_error(f'error: environment <s>"{venv.name}"</s> does not exist', 'error')
        return 1
      venv.delete()
      self.line_error(f'deleted environment <s>"{venv.name}"</s>', 'info')

    return 0


class VenvLinkCommand(Command):
  """ Link executables from a global virtual environment. """

  name = "venv link"
  arguments = [
    argument(
      "name",
      description="The global environment name.",
    ),
    argument(
      "program",
      description="The name of the program to link.",
    ),
  ]
  options = [
    option(
      "force", "f",
      description="Overwrite the link target if it already exists.",
    )
  ]

  def handle(self) -> int:
    manager = VenvManager(GLOBAL_VENVS_DIRECTORY)
    venv = manager.get(self.argument("name"))
    if not venv.exists():
      self.line_error(f'error: environment <s>"{venv.name}"</s> does not exist', 'error')
      return 1

    program = venv.get_bin(self.argument("program"))
    if not program.is_file():
      self.line_error(f'error: program <s>"{program.name}"</s> does not exist in environment <s>"{venv.name}"</s>', 'error')
      return 1

    target = GLOBAL_BIN_DIRECTORY / program.name
    if target.exists() and not self.option("force"):
      self.line_error(f'error: target <s>"{target}"</s> already exists', 'error')
      return 1

    if target.exists():
      target.unlink()
    target.symlink_to(program)
    self.line(f'symlinked <s>"{target}"</s> to <s>"{program}"</s>', 'info')

    return 0


class VenvPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    app.cleo.add(VenvCommand())
    app.cleo.add(VenvLinkCommand())
