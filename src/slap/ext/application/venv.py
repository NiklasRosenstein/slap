import logging
import os
import shutil
import string
import subprocess as sp
import typing as t
from pathlib import Path

from nr.python.environment.virtualenv import VirtualEnvInfo, get_current_venv

from slap.application import Application, Command, argument, option
from slap.plugins import ApplicationPlugin
from slap.python.environment import PythonEnvironment

logger = logging.getLogger(__name__)

GLOBAL_BIN_DIRECTORY = Path("~/.local/bin").expanduser()
GLOBAL_VENVS_DIRECTORY = Path("~/.local/venvs").expanduser()
SHADOW_INIT_SCRIPTS = {
    "bash": """
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
  """,
}

USER_INIT_SCRIPTS = {
    "bash": 'which slap >/dev/null && eval "$(SLAP_SHADOW=true slap venv -i bash)"',
}


class Venv(VirtualEnvInfo):
    def create(self, python_bin: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        sp.check_call([python_bin, "-m", "venv", self.path])

    def delete(self) -> None:
        shutil.rmtree(self.path)


class VenvManager:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or Path(".venvs")
        self.state_file = self.directory / ".state"

    def _get_state(self) -> dict[str, t.Any]:
        import json

        return json.loads(self.state_file.read_text()) if self.state_file.exists() else {}

    def _set_state(self, state: dict[str, t.Any]) -> None:
        import json

        self.state_file.write_text(json.dumps(state))

    def ls(self) -> t.Iterable[Venv]:
        if not self.directory.exists():
            return
        for path in self.directory.iterdir():
            if path.is_dir() and not path.name.startswith("."):
                yield Venv(path)

    def get(self, venv_name: str) -> Venv:
        return Venv(self.directory / venv_name)

    def get_last_activated(self) -> Venv | None:
        venv_name = self._get_state().get("last_active_environment")
        venv = self.get(venv_name) if venv_name else None
        return venv if venv and venv.exists() else None

    def set_last_activated(self, venv_name: str) -> None:
        state = self._get_state()
        state["last_active_environment"] = venv_name
        self._set_state(state)


class VenvAwareCommand(Command):
    """Base class for commands that should be aware of the active local virtual environment. Before the
    command is executed, it will check if we're currently in a virtual environment. If not, it will activate
    the environment that is considered "active" by the Slap `venv` command."""

    requires_venv: t.ClassVar[bool] = True

    options = [
        option(
            "no-venv-check",
            description="Do not check if the target Python environment is a virtual environment.",
        ),
        option(
            "ignore-active-venv",
            description="Ignore the currently active VIRTUAL_ENV and act as if it isn't set.",
        ),
        option(
            "use-venv",
            description="Use the specified Slap-managed virtual environment. This can be used to run a command "
            "in a seperate environment without activating or setting it as the current environment. Note that this "
            "option can not be used to run in a globally managed environment.",
            flag=False,
        ),
    ]

    def handle(self) -> int:
        if self.option("no-venv-check"):
            return 0
        venv = get_current_venv(os.environ)
        if (self.option("ignore-active-venv") or self.option("use-venv")) and venv:
            self.line(f"<info>(venv-aware) deactivating current virtual environment (<s>{venv.path}</s>)</info>")
            venv.deactivate(os.environ)
            venv = None
        if venv:
            self.io.error_output.write_line(
                "<info>(venv-aware) a virtual environment is already activated "
                f'(<s>{os.environ["VIRTUAL_ENV"]}</s>)</info>'
            )
        else:
            manager = VenvManager()
            if self.option("use-venv"):
                venv = manager.get(self.option("use-venv"))
                if not venv.exists():
                    self.io.error_output.write_line(f'<error>environment <s>"{venv.name}"</s> does not exist</error>')
                    return 1
            else:
                venv = manager.get_last_activated()
            if venv:
                venv.activate(os.environ)
                self.io.error_output.write_line(
                    f'<info>(venv-aware) activating current environment <s>"{venv.name}"</s></info>'
                )
            elif self.requires_venv:
                self.io.error_output.write_line(
                    "<warning>(venv-aware) there is no current environment that can be activated, use "
                    "`slap venv -s {env}` to set the current environment</warning>"
                )
                return 1
        return 0


class VenvCommand(Command):
    """Create, activate and remove virtual environments.

    This command makes it easy to create and manage virtual environments, locally as well
    as globally. Local environments are stored in the `.venvs/` directory in the current
    directory. Global environments are stored in `~/.local/venvs`.

    In order to be able to use the <opt>-a,--activate</opt> option directly from this command,
    it must be shadowed by a function in your shell. Use the <opt>-i,--init-code</opt> command
    to get a code snippet that you can place in your shell's init scripts.

    <u>Usage Example:</u>

        <code>$ slap venv -i bash >> ~/.profile; source ~/.profile
        $ slap venv -cg craftr
        <info>creating global environment <s>"craftr"</s> (using <code>python3</code>)</info>
        $ slap venv -lg</code>
        <info>1 environment in <s>"/home/niklas/.local/venvs"</s></info>
        • craftr   <code>3.10.2 (main, Jan 15 2022, 18:02:07) [GCC 9.3.0]</code>
        <code>$ slap venv -ag craftr
        (craftr) $ </code>

    Note that most Slap commands support using the active virtual environment it
    to be active in your shell (such as `slap run`, `slap test`, `slap install`,
    etc.).
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
            "--global",
            "-g",
            description="Manage virtual environments in the global scope instead of the local directory.",
        ),
        option(
            "--activate",
            "-a",
            description="Activate the environment given by the environment name. Note that using this option if used "
            "directly with the Slap CLI will cause an error because it needs to be shadowed by a function of your "
            "shell.",
        ),
        option(
            "--create",
            "-c",
            description="Create the environment with the given environment name. If no <opt>name</opt> is specified, "
            "the environment name will be the major.minor version of the current Python version.",
        ),
        option(
            "--delete",
            "-d",
            description="Delete the environment with the given environment name.",
        ),
        option(
            "--set",
            "-s",
            description="Similar to <opt>-a,--activate</opt>, but it will not activate the environment in your active "
            "shell even if you have the Slap shim installed (see <opt>-i,--init-code</opt>).",
        ),
        option(
            "--list",
            "-l",
            description="List the available environments.",
        ),
        option(
            "--path",
            "-p",
            description="Print the path of the specified or the current venv. Exit with status code 1 and no output if "
            "the environment does not exist or there is no current environment.",
        ),
        option("--exists", "-e", description="Return 0 if the specified environment exists, 1 otherwise."),
        option(
            "--init-code",
            "-i",
            description="Print the code snippet that can be placed in your shells init scripts to shadow this command "
            "in order to properly make use of the <opt>-a,--activate</opt> option. Currently supported shells are: "
            + ", ".join(USER_INIT_SCRIPTS),
            flag=False,
        ),
        option(
            "--python",
            description="The Python executable to use to create the virtual environment. If this is not specified, "
            "it defaults to <code>python</code> + the environment name if the environment name looks like a version "
            "number (contains numbers and dots). Otehrwise, it defaults to <code>python3</code>.",
            flag=False,
        ),
    ]

    def _validate_args(self) -> bool:
        for opt in ("activate", "create", "delete", "set", "exists"):
            if self.option("init-code") and self.option(opt):
                self.line_error(
                    f"error: <opt>-i,--init-code</opt> is not compatible with <opt>-{opt[0]},--{opt}</opt>", "error"
                )
                return False
            if self.option("list") and self.option(opt):
                self.line_error(
                    f"error: <opt>-l,--list</opt> is not compatible with <opt>-{opt[0]},--{opt}</opt>", "error"
                )
                return False
        for opt in ("delete", "set", "exists"):
            if self.option(opt) and not self.argument("name"):
                self.line_error("error: missing <opt>name</opt> argument", "error")
                return False
        for opt in ("activate", "create", "set", "exists"):
            if self.option("delete") and self.option(opt):
                self.line_error("error: <opt>-d,--delete</opt> is not compatible with <opt>--{opt}</opt>", "error")
                return False
        if self.option("path"):
            for opt in ("activate", "create", "delete", "set", "list", "init-code", "python", "exists"):
                if self.option(opt):
                    self.line_error("error: <opt>--path,-P</opt> is not compatible with <opt>--{opt}</opt>", "error")
                    return False
        if not any(
            self.option(opt) for opt in ("activate", "create", "delete", "set", "list", "init-code", "path", "exists")
        ):
            self.line_error("error: no operation specified", "error")
            return False
        return True

    def _get_python_bin(self) -> str:
        from slap.ext.application.install import get_active_python_bin

        python = get_active_python_bin(self, False)
        name = self.argument("name")
        if name and not python and set(name).issubset(string.digits + "."):
            python = f"python{name}"
        return python or "python3"

    def _list_environments(self, manager: VenvManager) -> None:
        venvs = list(manager.ls())
        if not venvs:
            self.line_error(f'no environments in <s>"{manager.directory}"</s>', "info")
            return
        self.line(f'{len(venvs)} environment{"s" if len(venvs) != 1 else ""} in <s>"{manager.directory}"</s>', "info")
        maxw = max(len(venv.name) for venv in venvs)
        for venv in venvs:
            self.line(f"• {venv.name.ljust(maxw)}  <code>{venv.get_python_version().splitlines()[0]}</code>")

    def _is_called_from_shadow(self) -> bool:
        return os.getenv("SLAP_SHADOW") == "true"

    def _get_init_code(self, shell: str) -> int:
        import textwrap

        source = SHADOW_INIT_SCRIPTS if self._is_called_from_shadow() else USER_INIT_SCRIPTS
        if shell in source:
            print(textwrap.dedent(source[shell]))
            return 0
        else:
            self.line_error(f"error: init code for shell <s>{shell}</s> is not supported", "error")
            return 1

    def _pick_venv(self, location: str, manager: VenvManager) -> Venv | None:
        """Picks either the last virtual environment that was activated, or the only one that is available."""

        venv = manager.get_last_activated()
        if venv and venv.exists():
            return venv

        venvs = list(manager.ls())
        if not venvs:
            self.line_error(f"error: no {location} environments", "error")
            return None

        if len(venvs) == 1:
            return venvs[0]

        self.line_error(f"error: multiple {location} environments exist, not sure which to pick", "error")
        return None

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
        venv = manager.get(self.argument("name")) if self.argument("name") else None
        location = "global" if self.option("global") else "local"

        if self.option("create"):
            if not venv:
                venv = manager.get(".".join(map(str, PythonEnvironment.of(python).version_tuple[:2])))
            if venv.exists():
                self.line_error(f'error: environment <s>"{venv.name}"</s> already exists', "error")
                return 1
            self.line_error(
                f'creating {location} environment <s>"{venv.name}"</s> (using <code>{python}</code>)', "info"
            )
            venv.create(python)

        if self.option("activate"):
            if not venv:
                venv = self._pick_venv(location, manager)
                if not venv:
                    return 1

            if not venv.exists():
                self.line_error(f'error: environment <s>"{venv.name}"</s> does not exist', "error")
                return 1

            if self._is_called_from_shadow():
                self.line_error(f'activating {location} environment <s>"{venv.name}"</s>', "info")
            else:
                self.line_error(
                    "warning: the <opt>-a,--activate</opt> option only works when shadowed by a shell function",
                    "warning",
                )

            # TODO (@NiklasRosenstein): Adjust output based on the shell that this is called from?
            # TODO (@NiklasRosenstein): Must be activate.cmd on Windows
            print(f'source "{venv.get_bin("activate")}"')
            manager.set_last_activated(venv.name)

        if self.option("delete"):
            if not venv:
                self.line_error("error: missing environment name", "error")
                return 1
            if not venv.exists():
                self.line_error(f'error: environment <s>"{venv.name}"</s> does not exist', "error")
                return 1
            venv.delete()
            self.line_error(f'deleted {location} environment <s>"{venv.name}"</s>', "info")

        if self.option("set"):
            assert venv is not None
            if not venv.exists():
                self.line_error(f'error: environment <s>"{venv.name}"</s> does not exist', "error")
                return 1
            manager.set_last_activated(venv.name)
            self.line_error(f'setting environment <s>"{venv.name}"</s> as active', "info")

        if self.option("path"):
            venv = venv or manager.get_last_activated()
            if not venv or not venv.exists():
                if venv and self.argument("name"):
                    self.line_error(f'error: environment <s>"{venv.name}"</s> does not exist', "error")
                else:
                    self.line_error("error: no active environment", "error")
                return 1
            print(venv.path.absolute())

        if self.option("exists"):
            assert venv is not None
            return 0 if venv.exists() else 1

        return 0


class VenvLinkCommand(Command):
    """Link executables from a global virtual environment."""

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
            "--global",
            "-g",
            description="Manage virtual environments in the global scope instead of the local directory.",
        ),
        option(
            "--force",
            "-f",
            description="Overwrite the link target if it already exists.",
        ),
    ]

    def handle(self) -> int:
        location = "global" if self.option("global") else "local"
        manager = VenvManager(GLOBAL_VENVS_DIRECTORY if self.option("global") else Path(".venvs"))
        venv = manager.get(self.argument("name"))
        if not venv.exists():
            self.line_error(f'error: {location} environment <s>"{venv.name}"</s> does not exist', "error")
            return 1

        program = venv.get_bin(self.argument("program"))
        if not program.is_file():
            self.line_error(
                f'error: program <s>"{program.name}"</s> does not exist in {location} environment <s>"{venv.name}"</s>',
                "error",
            )
            return 1

        target = GLOBAL_BIN_DIRECTORY / program.name
        exists = target.exists() or target.is_symlink()
        if exists and not self.option("force"):
            self.line_error(f'error: target <s>"{target}"</s> already exists', "error")
            return 1

        if exists:
            target.unlink()
        target.symlink_to(program.absolute())
        self.line(f'symlinked <s>"{target}"</s> to <s>"{program}"</s>', "info")

        return 0


class VenvPlugin(ApplicationPlugin):
    def load_configuration(self, app: Application) -> None:
        return None

    def activate(self, app: Application, config: None) -> None:
        app.cleo.add(VenvCommand())
        app.cleo.add(VenvLinkCommand())
