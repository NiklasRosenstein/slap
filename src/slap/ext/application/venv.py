from __future__ import annotations

import json
import logging
import os
import shutil
import string
import subprocess as sp
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from git import TYPE_CHECKING
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
      if [[ $? != 0 ]]; then
        >&2 echo "error: command 'slap' does not exist"
        return 127
      fi
      if [[ "$1" == "venv" && "$2" =~ -[gc]*a[gc]* ]]; then
        eval "$(SLAP_SHADOW=true "$ORIGINAL" "$@")"
      else
        "$ORIGINAL" "$@"
      fi
      return $?
    }
    """,
    "zsh": """
    function slap() {
      local ORIGINAL=$(command which slap)
      if [[ $? != 0 ]]; then
        >&2 echo "error: command 'slap' does not exist"
        return 127
      fi
      if [[ "$1" == "venv" && "$2" =~ -[gc]*a[gc]* ]]; then
        eval "$(SLAP_SHADOW=true "$ORIGINAL" "$@")"
      else
        "$ORIGINAL" "$@"
      fi
      return $?
    }
    """,
    "fish": """
    function slap
      set ORIGINAL (command which slap)
      if test $status -ne 0
        echo "error: command 'slap' does not exist" >&2
        return 127
      end
      if test (count $argv) -ge 2; and test $argv[1] = "venv"; and string match -qr -- '^-[gc]*a[gc]*' $argv[2]
        eval (env SLAP_SHADOW=true $ORIGINAL $argv)
      else
        $ORIGINAL $argv
      end
      return $status
    end
    """,
}

USER_INIT_SCRIPTS = {
    "bash": 'which slap >/dev/null && eval "$(SLAP_SHADOW=true slap venv -i bash)"',
    "zsh": 'which slap >/dev/null && eval "$(SLAP_SHADOW=true slap venv -i zsh)"',
    "fish": "command -v slap &>/dev/null; and source (env SLAP_SHADOW=true slap venv -i fish | psub)",
}


class VenvType(Enum):
    """The type of a virtual environment."""

    Uv = "uv"
    Venv = "venv"

    def new(self, path: Path, upgrade_on_create: bool) -> Venv:  # type: ignore[valid-type]  # ??
        match self:
            case VenvType.Uv:
                return UvVenv(path)
            case VenvType.Venv:
                return DefaultVenv(path, upgrade_on_create)
            case _:
                raise NotImplementedError(f"VenvType {self!r} is not implemented")


class Venv(VirtualEnvInfo, ABC):
    """Base class for managed virtual environments."""

    type: t.ClassVar[VenvType]

    @abstractmethod
    def _create(self, python_bin: str) -> None:
        raise NotImplementedError

    def create(self, python_bin: str) -> None:
        self._create(python_bin)
        metadata = {"type": self.type.value}
        self.path.joinpath("slap.json").write_text(json.dumps(metadata))

    def delete(self) -> None:
        shutil.rmtree(self.path)


class UvVenv(Venv):
    """A virtual environment managed by `uv` (https://github.com/astral-sh/uv)."""

    type = VenvType.Uv

    @staticmethod
    def find_uv_bin() -> Path:
        if TYPE_CHECKING:

            def find_uv_bin() -> str: ...

        else:
            from uv.__main__ import find_uv_bin

        return Path(find_uv_bin())

    def _create(self, python_bin: str) -> None:
        sp.check_call([str(self.find_uv_bin()), "venv", "--python", python_bin, str(self.path)])


@dataclass
class DefaultVenv(Venv):
    """A virtual environment managed by the built-in `venv` module."""

    type = VenvType.Venv

    upgrade: bool = True

    def _create(self, python_bin: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        command = [python_bin, "-m", "venv", str(self.path)]
        if self.upgrade:
            command += ["--upgrade"]
        sp.check_call(command)


class VenvManager:
    def __init__(self, venv_type: VenvType, directory: Path | None = None, upgrade_on_create: bool = True) -> None:
        """
        Args:
            directory: The directory in which the virtual environments are stored. If not specified, the default
                directory is `.venvs` in the current working directory.
            upgrade_on_create: If `True`, the `pip` package manager will be upgraded to the latest version after
                creating a new virtual environment. This only applies to environments created with the standard
                `venv` module.
        """

        self.directory = directory or Path(".venvs")
        self.state_file = self.directory / ".state"
        self.default_venv_type = venv_type
        self.upgrade_on_create = upgrade_on_create

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
                yield self.get(path.name)

    def get(self, venv_name: str) -> Venv:
        path = self.directory / venv_name
        metadata_file = path / "slap.json"
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text())
            venv_type = VenvType(metadata["type"])
            return venv_type.new(path, self.upgrade_on_create)
        return self.default_venv_type.new(path, self.upgrade_on_create)

    def get_last_activated(self) -> Venv | None:
        venv_name = self._get_state().get("last_active_environment")
        venv = self.get(venv_name) if venv_name else None
        return venv if venv and venv.exists() else None

    def set_last_activated(self, venv_name: str) -> None:
        state = self._get_state()
        state["last_active_environment"] = venv_name
        self._set_state(state)


def get_venv_manager(app: Application, default_venv_type: VenvType, upgrade_on_create: bool) -> VenvManager:
    """
    Returns the virtual environment manager for the given project.
    """

    project = app.main_project()
    if project is not None:
        if not project.shared_venv:
            return VenvManager(default_venv_type, project.directory / ".venvs", upgrade_on_create)
    return VenvManager(default_venv_type, app.repository.directory / ".venvs", upgrade_on_create)


def get_venv_manager_global_or_local(
    use_global: bool, app: Application, default_venv_type: VenvType, upgrade_on_create: bool
) -> VenvManager:
    if use_global:
        return VenvManager(default_venv_type, GLOBAL_VENVS_DIRECTORY, upgrade_on_create)
    else:
        return get_venv_manager(app, default_venv_type, upgrade_on_create)


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

    current_venv: Venv | None = None

    def __init__(self, app: Application) -> None:
        super().__init__()
        self.app = app

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
            metadata_file = venv.path / "slap.json"
            if metadata_file.exists():
                venv_type = VenvType(json.loads(metadata_file.read_text())["type"])
                self.current_venv = venv_type.new(venv.path, True)
            else:
                self.current_venv = DefaultVenv(venv.path, True)
        else:
            from slap.ext.application.config import get_config

            manager = get_venv_manager(self.app, get_config().get_venv_type() or VenvType.Venv, upgrade_on_create=True)
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
                    "<info>slap venv -s {env}</info> to set the current environment</warning>"
                )
                return 1
            self.current_venv = venv
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

        <code>$ slap venv -i bash >> ~/.profile; source ~/.profile                                 # for bash
        $ slap venv -i zsh >> ~/.zshrc; source ~/.zshrc                                      # for zsh
        $ slap venv -i fish >> ~/.config/fish/config.fish; source ~/.config/fish/config.fish # for fish
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
            "--venv-type",
            description="The type of virtual environment to create. [venv|uv]",
            flag=False,
        ),
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
        option("--no-upgrade-pip", description="If specified, will not upgrade Pip after creating a new environment."),
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

    def __init__(self, app: Application) -> None:
        super().__init__()
        self.app = app

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
        if self.option("no-upgrade-pip") and not self.option("create"):
            self.line_error(
                "error: <opt>--no-pip-upgrade</opt> is only valid in combination with <opt>-c,--create</opt>"
            )
            return False
        if not any(
            self.option(opt) for opt in ("activate", "create", "delete", "set", "list", "init-code", "path", "exists")
        ):
            self.line_error("error: no operation specified", "error")
            return False
        if venv_type_str := self.option("venv-type"):
            venv_type_str = venv_type_str.lower()
            try:
                VenvType(venv_type_str)
            except ValueError:
                self.line_error("error: invalid virtual environment type: %r" % venv_type_str, "error")
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

        if venv_type_str := self.option("venv-type"):
            venv_type = VenvType(venv_type_str.lower())
        else:
            from slap.ext.application.config import get_config

            config = get_config()
            venv_type = config.get_venv_type() or VenvType.Venv

        manager = get_venv_manager_global_or_local(
            self.option("global"),
            self.app,
            default_venv_type=venv_type,
            upgrade_on_create=True,
        )

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
            #                (@jonhoo): Possibly based on something more reliable than last component of $SHELL?
            # TODO (@NiklasRosenstein): Must be activate.cmd on Windows
            if os.environ.get("SHELL", "sh").endswith("fish"):
                print(f'source "{venv.get_bin("activate.fish")}"')
            else:
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

    def __init__(self, app: Application) -> None:
        super().__init__()
        self.app = app

    def handle(self) -> int:
        from slap.ext.application.config import get_config

        location = "global" if self.option("global") else "local"
        manager = get_venv_manager_global_or_local(
            self.option("global"), self.app, get_config().get_venv_type() or VenvType.Venv, True
        )
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
        app.cleo.add(VenvCommand(app))
        app.cleo.add(VenvLinkCommand(app))
