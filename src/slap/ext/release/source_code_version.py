import logging

from slap.plugins import ReleasePlugin
from slap.project import Project
from slap.release import VersionRef, match_version_ref_pattern

logger = logging.getLogger(__name__)


class SourceCodeVersionReferencesPlugin(ReleasePlugin):
    """This plugin searches for a `__version__` key in the source code of the project and return it as a version
    reference. Based on the Poetry configuration (considering `tool.poetry.packages` and searching in the `src/`
    folder if it exists), the following source files will be checked:

    * `__init__.py`
    * `__about__.py`
    * `_version.py`

    Note that configuring `tool.poetry.packages` is needed for the detection to work correctly with PEP420
    namespace packages.
    """

    VERSION_REGEX = r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]'
    FILENAMES = ["__init__.py", "__about__.py", "_version.py", ".py"]

    def get_version_refs(self, project: Project) -> list[VersionRef]:
        packages = project.packages()
        if not packages:
            return []

        results = []
        packages_without_version = []
        for package in packages:
            for path in [package.path] if package.path.is_file() else [package.path / f for f in self.FILENAMES]:
                if path.exists():
                    try:
                        version_ref = match_version_ref_pattern(path, self.VERSION_REGEX)
                    except ValueError as exc:
                        logger.warning("%s", exc)
                        continue
                    if version_ref:
                        results.append(version_ref)
                        break
            else:
                packages_without_version.append(package)

        if packages_without_version:
            logger.warning(
                "Unable to detect <val>__version__</val> in the following packages of project "
                "<subj>%s</sub>: <obj>%s</obj>",
                project,
                [p.name for p in packages_without_version],
            )

        return results
