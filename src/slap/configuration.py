from __future__ import annotations

import logging
import typing as t
from pathlib import Path

from slap.util.toml_file import TomlFile

if t.TYPE_CHECKING:
    from slap.util.once import Once

logger = logging.getLogger(__name__)


class Configuration:
    """Represents the configuration stored in a directory, which is either read from `slap.toml` or `pyproject.toml`."""

    id: str

    #: The directory of the project. This is the directory where the `slap.toml` or `pyproject.toml` configuration
    #: would usually reside in, but the existence of neither is absolutely required.
    directory: Path

    #: Points to the `pyproject.toml` file in the project and can be used to conveniently check for its existence
    #: or to access its contents.
    pyproject_toml: TomlFile

    #: Points to the `slap.toml` file in the project and can be used to conveniently check for its existence
    #: or to access its contents.
    slap_toml: TomlFile

    #: Use this to access the Slap configuration, automatically loaded from either `slap.toml` or the `tool.slap`
    #: section in `pyproject.toml`. The attribute is a #Once instance, thus it needs to be called to retrieve
    #: the contents. This is the same as #get_raw_configuration(), but is more efficient.
    raw_config: Once[dict[str, t.Any]]

    def __init__(self, directory: Path) -> None:
        from slap.util.once import Once

        self.directory = directory
        self.pyproject_toml = TomlFile(directory / "pyproject.toml")
        self.slap_toml = TomlFile(directory / "slap.toml")
        self.raw_config = Once(self.get_raw_configuration)

    def __repr__(self) -> str:
        return f'{type(self).__name__}(directory="{self.directory}")'

    def get_raw_configuration(self) -> dict[str, t.Any]:
        """Loads the raw configuration data for Slap from either the `slap.toml` configuration file or `pyproject.toml`
        under the `[slap.tool]` section. If neither of the files exist or the section in the pyproject does not exist,
        an empty dictionary will be returned."""

        if self.slap_toml.exists():
            logger.debug("Reading configuration for <subj>%s</subj> from <val>%s</val>", self, self.slap_toml.path)
            return self.slap_toml.value()
        if self.pyproject_toml.exists():
            logger.debug("Reading configuration for <subj>%s</subj> from <val>%s</val>", self, self.pyproject_toml.path)
            return self.pyproject_toml.value().get("tool", {}).get("slap", {})
        return {}
