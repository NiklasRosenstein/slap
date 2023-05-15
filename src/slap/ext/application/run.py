from __future__ import annotations

import logging
import shlex
import subprocess as sp
from pathlib import Path
from typing import ClassVar

from slap.application import Application, argument
from slap.ext.application.venv import VenvAwareCommand
from slap.plugins import ApplicationPlugin

logger = logging.getLogger(__name__)


class RunCommandPlugin(VenvAwareCommand, ApplicationPlugin):
    """Run a command in the current active environment. If the command name is an alias
    configured in <code>[tool.slap.run]</code>, run it instead.

    In order to pass command-line options and flags, you need to add an addition `--` to
    ensure that arguments following it are parsed as positional arguments.

    Example:

        $ slap run pytest -- -vv
    """

    name: str = "run"
    requires_venv: ClassVar[bool] = True

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

        main_project = self.app.main_project()
        commands_to_execute = {}
        working_dirs = {}

        command: list[str] = self.argument("args")
        if main_project and command[0] in self.config:
            command_string = self.config[command[0]] + " " + _join_args(command[1:])
            commands_to_execute[main_project.id if main_project else "/"] = command_string
            working_dirs[main_project.id if main_project else "/"] = Path.cwd()
        elif not main_project:
            for project in self.app.configurations(targets_only=True):
                config = project.raw_config().get("run", {})
                if command[0] in config:
                    command_string = config[command[0]] + " " + _join_args(command[1:])
                    commands_to_execute[project.id] = command_string
                    working_dirs[project.id] = project.directory

        if not commands_to_execute:
            commands_to_execute["$"] = _join_args(command)
            working_dirs["$"] = Path.cwd()

        if len(commands_to_execute) > 1:
            level = logging.WARNING
        else:
            level = logging.INFO

        results = {}
        for key, command_string in commands_to_execute.items():
            logger.log(level, "(%s) Running command: $ %s", key, command_string)
            results[key] = sp.call(command_string, shell=True, cwd=working_dirs[key])

        if any(x != 0 for x in results.values()):
            level = logging.WARNING
            exit_code = results[next(iter(results))] if len(results) == 1 else 127
            status = "FAILED"
        else:
            level = logging.INFO
            exit_code = 0
            status = "SUCCESS"

        if len(results) == 1:
            logging.log(level, "Exit code: %s (status: %s)", exit_code, status)
        else:
            logging.log(level, "Multi-run results: (status: %s)", status)
            for key in results:
                logging.log(level, "  %s: %s", key, results[key])

        return exit_code


def _join_args(args: list[str]) -> str:
    return " ".join(map(shlex.quote, args))
