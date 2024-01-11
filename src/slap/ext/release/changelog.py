import typing as t
from pathlib import Path

from slap.ext.application.changelog import get_changelog_manager
from slap.plugins import ReleasePlugin
from slap.project import Project
from slap.repository import Repository


class ChangelogReleasePlugin(ReleasePlugin):
    """Renames the `_unreleased.toml` file when a release is created."""

    def create_release(
        self, repository: Repository, project: Project | None, target_version: str, dry: bool
    ) -> t.Sequence[Path]:
        changed_files: list[Path] = []

        config_sources: list[Project | None] = [*repository.projects()] if project is None else [project]
        if repository.is_monorepo and project is None:
            config_sources.append(None)

        for project in config_sources:
            manager = get_changelog_manager(repository, project)
            unreleased = manager.unreleased()
            if unreleased.path in changed_files:
                # We hit this case in a single-project repository, where "None" and the single project will
                # both return the same changelog manager.
                continue
            new_version = manager.version(target_version)
            if unreleased.exists():
                cwd = Path.cwd()
                old = unreleased.path.relative_to(cwd)
                new = new_version.path.relative_to(cwd)
                if not changed_files:
                    self.io.write_line("releasing changelog")
                self.io.write_line(f"  <fg=cyan>{old}</fg> → <b>{new}</b>")
                if not dry:
                    unreleased.release(target_version)
                changed_files += [unreleased.path, new_version.path]
        return changed_files
