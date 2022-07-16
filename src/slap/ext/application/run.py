from __future__ import annotations

import shlex
import subprocess as sp
from typing import ClassVar

from slap.application import Application, argument
from slap.ext.application.venv import VenvAwareCommand
from slap.plugins import ApplicationPlugin


class RunCommandPlugin(VenvAwareCommand, ApplicationPlugin):
    """Run a command in the current active environment. If the command name is an alias
    configured in <code>[tool.slap.run]</code>, run it instead.

    In order to pass command-line options and flags, you need to add an addition `--` to
    ensure that arguments following it are parsed as positional arguments.

    Example:

        $ slap run pytest -- -vv
    """

    name: str = "run"
    requires_venv: ClassVar[bool] = False

    arguments = [
        argument(
            "args",
            description="Command name and arguments.",
            multiple=True,
        )
    ]

    def load_configuration(self, app: Application) -> dict[str, str]:
        config = (app.main_project() or app.repository).raw_config()
        return config.get("run", {})

    def activate(self, app: Application, config: dict[str, str]) -> None:
        self.app = app
        self.config = config
        app.cleo.add(self)

    def handle(self) -> int:
        result = super().handle()
        if result != 0:
            return result
        command: list[str] = self.argument("args")
        if command[0] in self.config:
            command_string = self.config[command[0]] + " " + _join_args(command[1:])
        else:
            command_string = _join_args(command)
        return sp.call(command_string, shell=True)


def _join_args(args: list[str]) -> str:
    return " ".join(map(shlex.quote, args))
