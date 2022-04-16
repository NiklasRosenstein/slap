from __future__ import annotations

import importlib
import os
import typing as t
from pathlib import Path


class _BackendApi:
    def build_sdist(self, sdist_directory: str, config_settings: dict | None) -> str:
        ...

    def build_wheel(
        self, wheel_directory: str, config_settings: dict | None, metadata_directory: str | None = None
    ) -> str:
        ...


class BuildBackend:
    """An API to interface with a [PEP 517][] build backend.

    Note that the build backend module must be importable by the Python environment that is using this class.

    [PEP 517]: https://www.python.org/dev/peps/pep-0517/
    """

    def __init__(self, backend_name: str, project_directory: Path, build_directory: Path) -> None:
        """
        Args:
          backend_name: The build backend module name.
          project_directory: The project directory that contains the build source files.
          build_directory: The build output directory.
        """

        self.backend_name = backend_name
        self.project_directory = project_directory.resolve()
        self.build_directory = build_directory.resolve()
        self._module = t.cast(_BackendApi, importlib.import_module(backend_name))

    def __repr__(self) -> str:
        return f'BuildBackend("{self.backend_name}")'

    def build_sdist(self, config_settings: dict[str, str | list[str]] | None = None) -> Path:
        """Build a source distribution."""

        old_cwd = Path.cwd()
        try:
            os.chdir(self.project_directory)
            filename = self._module.build_sdist(str(self.build_directory), config_settings)
            return self.build_directory / filename
        finally:
            os.chdir(old_cwd)

    def build_wheel(self, config_settings: dict[str, str | list[str]] | None = None) -> Path:
        """Build a wheel distribution."""

        old_cwd = Path.cwd()
        try:
            os.chdir(self.project_directory)
            filename = self._module.build_wheel(str(self.build_directory), config_settings, None)
            return self.build_directory / filename
        finally:
            os.chdir(old_cwd)
