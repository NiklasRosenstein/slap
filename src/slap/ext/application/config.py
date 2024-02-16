from pathlib import Path
from typing import Any

import tomli
import tomli_w

from slap.application import Application, Command, option
from slap.ext.application.venv import VenvType
from slap.plugins import ApplicationPlugin

CONFIG_FILE = Path.home() / ".config" / "slap" / "config.toml"


def get_config() -> "ConfigModel":
    config = ConfigModel(CONFIG_FILE)
    config.load()
    return config


class ConfigModel:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] | None = {}

    def load(self) -> None:
        if self.path.exists():
            with self.path.open("rb") as file:
                self.data = tomli.load(file)
        else:
            self.data = {}

    def save(self) -> None:
        assert self.data is not None
        self.path.parent.mkdir(exist_ok=True, parents=True)
        with self.path.open("wb") as file:
            tomli_w.dump(self.data, file)

    def set_venv_type(self, venv_type: VenvType) -> None:
        assert self.data is not None
        self.data["venv_type"] = venv_type.value

    def get_venv_type(self) -> VenvType | None:
        assert self.data is not None
        value = self.data.get("venv_type")
        return VenvType(value) if value is not None else None


class SlapConfigCommand(ApplicationPlugin, Command):
    """Command to manage global user configuration."""

    name = "config"

    options = [
        option(
            "--venv-type",
            description="Set the default type of virtual environment to create. [venv|uv]",
            flag=False,
        )
    ]

    def __init__(self, app: Application) -> None:
        ApplicationPlugin.__init__(self, app)
        Command.__init__(self)

    def handle(self) -> int:
        model = ConfigModel(CONFIG_FILE)
        model.load()

        if venv_type := self.option("venv-type"):
            try:
                model.set_venv_type(VenvType(venv_type.lower()))
            except ValueError:
                self.line_error(f"Invalid virtual environment type: {venv_type}.")
                return 1
            model.save()
            self.line(f"Default virtual environment type set to {venv_type}.")
            return 0

        self.line_error("No option provided.")
        return 1

    def load_configuration(self, app: Application) -> Any:
        return None

    def activate(self, app: Application, config: Any) -> None:
        app.cleo.add(SlapConfigCommand(app))
