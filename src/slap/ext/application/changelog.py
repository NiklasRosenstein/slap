import dataclasses
import io
import logging
import re
import sys
import typing as t
from pathlib import Path

from databind.core.settings import Alias, ExtraKeys

from slap.application import Application, Command, argument, option
from slap.changelog import Changelog, ChangelogEntry, ChangelogManager, ManagedChangelog
from slap.plugins import ApplicationPlugin, RepositoryCIPlugin
from slap.project import Project
from slap.repository import Issue, PullRequest, Repository
from slap.util.pygments import toml_highlight
from slap.util.vcs import Vcs

logger = logging.getLogger(__name__)

#: The default set of types a changelog entry can have.
DEFAULT_VALID_TYPES = [
    "breaking change",
    "deprecation",
    "docs",
    "feature",
    "fix",
    "hygiene",
    "improvement",
    "refactor",
    "tests",
]


def get_default_author(app: Application) -> str | None:
    username: str | None = None
    if remote := app.repository.host():
        try:
            username = remote.get_username(app.repository)
        except Exception as exc:
            logger.warning(
                f"unable to fetch GitHub username, falling back to configured email address. (reason: {exc})"
            )
    if username is None and (vcs := app.repository.vcs()):
        username = vcs.get_author().email
    return username


@ExtraKeys(True)
@dataclasses.dataclass
class ChangelogConfig:
    #: Whether the changelog feature is enabled. This acts locally for the current project and not globally.
    #: Particularly useful for monorepos that have multiple subprojects each with their changelog directories
    #: to prevent accidentally creating changelogs in the root directory.
    #:
    #: When not set, it will be considered `True` if the current project is a Python project.
    enabled: bool | None = None

    #: The directory in which changelogs are stored.
    directory: Path = Path(".changelog")

    #: The list of valid types that can be used in changelog entries. The default types are
    #: #DEFAULT_CHANGELOG_TYPES.
    valid_types: t.Annotated[list[str] | None, Alias("valid-types")] = dataclasses.field(
        default_factory=lambda: list(DEFAULT_VALID_TYPES)
    )


class BaseChangelogCommand(Command):
    def __init__(self, app: Application, manager: ChangelogManager) -> None:
        super().__init__()
        self.app = app
        self.manager = manager


class ChangelogAddCommand(BaseChangelogCommand):
    """Add an entry to the unreleased changelog via the CLI.

    A changelog is a TOML file, usually in the <u>.changelog/</u> directory, named with
    the version number it refers to and containing changelog entries. Changes that
    are currently not released in a version are stored in a file called
    <u>_unreleased.toml</u>.

    Changelog entries contain at least one author, a type (e.g. whether the entry
    describes a feature, enhancement, bug fix, etc.) and optionally a subject (e.g.
    whether the change is related to docs or a particular component of the code), a
    Markdown description, possibly a link to a pull request with which the change
    was introduced and links to issues that the changelog addresses.

    <b>Example:</b>

      <fg=blue># .changelog/0.1.1.toml</fg>
      <fg=cyan>[changelog]</fg>
      <fg=green>release-date</fg> = <fg=yellow>"2022-01-17"</fg>

      <fg=cyan>[[changelog.entries]]</fg>
      <fg=green>id</fg> = <fg=yellow>"a7bc01f"</fg>
      <fg=green>type</fg> = <fg=yellow>"improvement"</fg>
      <fg=green>description</fg> = <fg=yellow>"Improvement to `my_package.util`"</fg>
      <fg=green>author</fg> = <fg=yellow>"username"</fg>
      <fg=green>pr</fg> = <fg=yellow>"https://github.com/username/my_package/pulls/13"</fg>

    Changelog entries can be managed easily using the <info>slap changelog</info> command.

      <fg=yellow>$</fg> slap changelog add -t feature -d 'Improvement to `my_package.util`"

    The <fg=green>pr</fg> field is usually set manually after the PR is created or updated
    automatically by a CI action using the <info>slap changelog update-pr-field</info> command.
    """

    name = "changelog add"

    options = [
        option(
            "--type",
            "-t",
            description="The type of the changelog. Unless configured differently, one of: "
            f"{', '.join(DEFAULT_VALID_TYPES)}",
            flag=False,
        ),
        option(
            "--description",
            "-d",
            description="A Markdown formatted description of the changelog entry.",
            flag=False,
        ),
        option(
            "--author",
            "-a",
            description="Your username or email address. By default, this will be your configured "
            "Git name and email address.",
            flag=False,
        ),
        option(
            "--pr",
            None,
            description="The pull request that the change is introduced to the main branch with. This is not usually "
            "known at the time the changelog entry is created, so this option is not often used. If the remote "
            "repository is well supported by Slap, a pull request number may be specified and converted to a full "
            "URL by Slap, otherwise a full URL must be specified.",
            flag=False,
        ),
        option(
            "--issue",
            "-i",
            description="An issue related to this changelog. If the remote repository is well supported by Slap, "
            "an issue number may be specified and converted to a full URL by Slap, otherwise a full URL must be "
            "specified.",
            flag=False,
            multiple=True,
        ),
        option(
            "--commit",
            "-c",
            description="Commit the currently staged changes in the VCS as well as the updated changelog file to disk. "
            "The commit message is a concatenation of the <opt>--type, -t</opt> and <opt>--description, -d</opt>, as "
            "well as the directory relative to the VCS toplevel if the changelog is created not in the toplevel "
            "directory of the repository.",
        ),
        option(
            "--component",
            "-C",
            description="The name of the component that the changelog is about.",
            flag=False,
        ),
    ]

    def handle(self) -> int:
        if self.manager.readonly:
            self.line_error("error: cannot add changelog because the feature must be enabled in the config", "error")
            return 1

        vcs = self.app.repository.vcs()
        change_type: str | None = self.option("type")
        description: str | None = self.option("description")
        author: str | None = self.option("author") or get_default_author(self.app)
        pr: str | None = self.option("pr")
        issues: list[str] | None = self.option("issue")
        component: str | None = self.option("component")

        if not vcs and self.option("commit"):
            self.line_error("error: no VCS detected, but <opt>--commit, -c</opt> was used", "error")
            return 1

        if not change_type:
            self.line_error("error: missing <opt>--type,-t</opt>", "error")
            return 1
        if not description:
            self.line_error("error: missing <opt>--description,-d</opt>", "error")
            return 1
        if not author:
            self.line_error("error: missing <opt>--author,-a</opt>", "error")
            return 1

        entry = self.manager.make_entry(change_type, description, author, pr, issues, component)
        unreleased = self.manager.unreleased()
        changelog = unreleased.content if unreleased.exists() else Changelog()
        changelog.entries.append(entry)
        unreleased.save(changelog)

        print(toml_highlight(self.manager.deser.dump_entry(entry)))

        if self.option("commit"):
            assert vcs is not None
            commit_message = f"{change_type}: {description}"
            main_project = self.app.main_project()
            relative = main_project.directory.relative_to(self.app.repository.directory) if main_project else Path(".")
            if relative != Path("."):
                prefix = str(relative).replace("\\", "/").strip("/")
                commit_message = f"{prefix}/: {commit_message}"
            vcs.commit_files([unreleased.path], commit_message)

        return 0


@dataclasses.dataclass
class ChangelogDiff:
    added_entries: list[ChangelogEntry] = dataclasses.field(default_factory=list)
    removed_entries: list[ChangelogEntry] = dataclasses.field(default_factory=list)
    updated_entries: list[tuple[ChangelogEntry, ChangelogEntry]] = dataclasses.field(default_factory=list)
    unchanged_entries: list[ChangelogEntry] = dataclasses.field(default_factory=list)


class ChangelogDiffBaseCommand(Command):
    """Base class for commands that perform changelog diffs."""

    arguments = [
        argument(
            "ref_or_range",
            description="The Git ref or Git range (formatted as BASE..HEAD) to look inspect the diff for. If only "
            "a Git ref is specified, the diff between that ref and the current worktree is used. The "
            "<code>--use</code> option can be used in a compatible CI environment to automatically derive the base "
            "Git ref in Pull Requests.",
            optional=True,
        ),
    ]

    options = [
        option(
            "--use",
            description="Use the specified plugin for interacting with the Git repository host. Use this in "
            "supported CI environments instead of manually configuring the command-line settings. You can list "
            "the available plugins with the <info>changelog pr plugins</info> command.",
            flag=False,
        ),
    ]

    def __init__(self, app: Application) -> None:
        super().__init__()
        self.app = app
        self.managers = {
            config: get_changelog_manager(app.repository, config if isinstance(config, Project) else None)
            for config in app.configurations()
        }
        self.ci: RepositoryCIPlugin | None
        self.base_ref: str
        self.head_ref: str | None
        self.vcs: Vcs

    def validate_arguments(self) -> None:
        """Validates the arguments to the command to populates relevant attributes."""

        plugin_name: str | None = self.option("use")
        if plugin_name is not None:
            logger.info("Loading changelog update automation plugin <i>%s</i>", plugin_name)
            try:
                self.ci = RepositoryCIPlugin.get(plugin_name, self.io)
            except ValueError:
                self.line_error(f"plugin `<info>{plugin_name}</info>` does not exist.", "error")
                sys.exit(1)
        else:
            self.ci = None

        ref_or_range: str | None = self.argument("ref_or_range")
        if ref_or_range is not None:
            base_revision, sep, head_revision = ref_or_range.partition("..")
            if sep and not head_revision:
                self.line_error(f"invalid Git range: <code>{ref_or_range}</code>", "error")
                sys.exit(1)
            self.base_ref = base_revision
            self.head_ref = head_revision or None
        else:
            if self.ci is None:
                self.line_error("Need a base Git ref, Git range or set the --use option.", "error")
                sys.exit(1)
            self.base_ref = self.ci.get_base_ref()
            self.head_ref = self.ci.get_head_ref()

        if self.head_ref is None:
            self.ref_range = f"{self.base_ref}..WORKTREE"
        else:
            self.ref_range = f"{self.base_ref}..{self.head_ref}"

        vcs = self.app.repository.vcs()
        if not vcs:
            self.line_error("VCS is not configured or could not be detected", "error")
            sys.exit(1)
        self.vcs = vcs

    def get_diff(self, manager: ChangelogManager) -> ChangelogDiff:
        """Calculates the difference in the unreleased changelogs for the given changelog manager."""

        changelog_path = manager.unreleased().path

        # Load the old changelog contents.
        old_changelog: Changelog | None = None
        old_data = self.vcs.get_file_contents(changelog_path, self.base_ref)
        if old_data is not None:
            old_changelog = manager.load(io.StringIO(old_data.decode()))

        # Load the new changelog contents.
        new_changelog: Changelog | None = None
        if self.head_ref:
            new_data = self.vcs.get_file_contents(changelog_path, self.head_ref)
            if new_data is not None:
                new_changelog = manager.load(io.StringIO(new_data.decode()))
        elif changelog_path.is_file():
            new_changelog = manager.load(changelog_path)

        old_entries = {e.id: e for e in old_changelog.entries} if old_changelog else {}
        new_entries = {e.id: e for e in new_changelog.entries} if new_changelog else {}

        diff = ChangelogDiff()
        for entry_id in {*old_entries, *new_entries}:
            if entry_id in old_entries and entry_id in new_entries:
                if old_entries[entry_id] == new_entries[entry_id]:
                    diff.unchanged_entries.append(old_entries[entry_id])
                else:
                    diff.updated_entries.append((old_entries[entry_id], new_entries[entry_id]))
            elif entry_id not in new_entries:
                diff.removed_entries.append(old_entries[entry_id])
            elif entry_id not in old_entries:
                diff.added_entries.append(new_entries[entry_id])
            else:
                assert False, "whaat?"

        return diff


class ChangelogDiffUpdatePrCommand(ChangelogDiffBaseCommand):
    """Update the <code>pr</code> field of changelog entries in a commit range.

    Updates all changelog entries that were added in a given commit range in the
    unreleased changelog. This is useful to run in CI for a pull request to avoid
    having to manually update the changelog entry after the PR has been created.
    """

    name = "changelog diff pr update"

    options = ChangelogDiffBaseCommand.options + [
        option(
            "--dry",
            "-d",
            description="Do not actually make changes on disk.",
        ),
        option(
            "--overwrite",
            description="Update PR references even if an entry's reference is already set but different.",
        ),
        option(
            "--pr",
            description="The PR URL to set. If not set, the <opt>--use</opt> option must be specified.",
            flag=False,
        ),
    ]

    def validate_arguments(self) -> None:
        super().validate_arguments()

        pr_url: str | None = self.option("pr")
        if pr_url is None:
            if self.ci is None:
                self.line_error("need <opt>--pr</opt> or <opt>--use</opt>", "error")
                sys.exit(1)
            pr_url = self.ci.get_pr()
        self.pr_url = pr_url

    def handle(self) -> int:
        self.validate_arguments()

        total_updates = 0
        changed_files: list[Path] = []

        for manager in self.managers.values():
            changelog_ref = manager.unreleased()
            if not changelog_ref.exists():
                continue

            num_updates = 0
            changelog = changelog_ref.load()
            diff = self.get_diff(manager)
            for entry_id in (e.id for e in diff.added_entries):
                entry = changelog.find_entry(entry_id)
                if entry is None:
                    self.line_error(
                        f"Changelog entry <code>{entry_id}</code> found in diff does not " "exist in worktree.",
                        "warning",
                    )
                    continue
                if entry.pr is None or self.option("overwrite"):
                    entry.pr = self.pr_url
                    num_updates += 1
                    total_updates += 1

            if not self.option("dry") and num_updates > 0:
                self.line(f"updated <i>{num_updates}</i> entries in <fg=yellow>{changelog_ref.path}</fg>", "info")
                changelog_ref.save(changelog)
                changed_files.append(changelog_ref.path)

        if total_updates == 0:
            self.line("no entries to update", "info")
            return 0

        if self.ci and not self.option("dry"):
            plural = "" if total_updates == 0 else "s"
            commit_message = f"Updated PR reference{plural} in {num_updates} changelog{plural}."
            self.ci.publish_changes(changed_files, commit_message)

        return 0


class ChangelogDiffAssertCommand(ChangelogDiffBaseCommand):
    """This command can be used to assert that changelog entries have been added
    in a Git revision range."""

    name = "changelog diff assert-added"

    def handle(self) -> int:
        self.validate_arguments()
        added: list[ChangelogEntry] = []
        for manager in self.managers.values():
            diff = self.get_diff(manager)
            added += diff.added_entries
        if not added:
            self.line_error(f"no changelog entries have been added in <code>{self.ref_range}</code>", "error")
            return 1
        self.line(f"<i>{len(added)}</i> changelog entries added in <code>{self.ref_range}</code>\n")
        for entry in added:
            print("*", entry.description)
            print()
        return 0


class ChangelogFormatCommand(BaseChangelogCommand):
    """Format the changelog in the terminal or in Markdown format."""

    name = "changelog format"
    options = [
        option(
            "--markdown",
            "-m",
            description="Render the changelog in Markdown format.",
        ),
        option(
            "--all",
            "-a",
            description="Render all changelogs in reverse chronological order.",
        ),
    ]
    arguments = [
        argument("version", "The changelog version to format.", optional=True),
    ]

    def handle(self) -> int:
        if not self._validate_arguments():
            return 1

        if self.option("all"):
            changelogs = self.manager.all()
        elif version := self.argument("version"):
            changelogs = [self.manager.version(version)]
            if not changelogs[0].exists():
                self.line_error(f'error: Changelog for <opt>version</opt> "{version}" does not exist.', "error")
                return 1
        else:
            changelogs = [self.manager.unreleased()]

        for changelog in changelogs:
            if self.option("markdown"):
                self._render_markdown(changelog)
            else:
                self._render_terminal(changelog)
            self.line("")

        return 0

    def _validate_arguments(self) -> bool:
        if self.option("all") and self.argument("version"):
            self.line_error("error: <opt>--all, -a</opt> is incompatible with <opt>version</opt> argument", "error")
            return False
        return True

    def _render_terminal(self, changelog: ManagedChangelog) -> None:
        if changelog.version:
            assert changelog.content.release_date
            self.line(f"<b>{changelog.version}</b> (<u>{changelog.content.release_date}</u>)")
        else:
            self.line(f'<b>{changelog.version or "Unreleased"}</b>')
            if not changelog.exists():
                return

        for entry in changelog.content.entries:
            description = entry.description
            description = re.sub(r"(?!<\\)`([^`]+)`", r"<fg=dark_gray>\1</fg>", description)
            self.line(f"  <fg=cyan;options=italic>{entry.type}</fg> — {description} (<fg=yellow>{entry.author}</fg>)")

    def _render_markdown(self, changelog: ManagedChangelog) -> None:
        if changelog.version:
            assert changelog.content.release_date
            print(f"## {changelog.version} ({changelog.content.release_date})")
        else:
            print("## Unreleased")
            if not changelog.exists():
                return

        print()
        print("<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>")
        for entry in changelog.content.entries:
            pr_link = self._html_anchor("pr", entry.pr) if entry.pr else ""
            issues = ", ".join(self._html_anchor("issue", issue) for issue in entry.issues) if entry.issues else ""
            print(
                f"  <tr><td>{entry.type.capitalize()}</td><td>\n\n{entry.description}</td>"
                f'<td>{pr_link}</td><td>{issues}</td><td>{", ".join(entry.get_authors())}</td></tr>'
            )
        print("</table>")

    def _html_anchor(self, type: t.Literal["pr", "issue"], ref: str) -> str:
        if self.manager.repository_host:
            try:
                if type == "pr":
                    item: Issue | PullRequest = self.manager.repository_host.get_pull_request_by_reference(ref)
                else:
                    item = self.manager.repository_host.get_issue_by_reference(ref)
            except ValueError as exc:
                self.line_error(f"warning: {exc}", "error")
                url = ref
                text = "Link"
            else:
                url, text = item.url, item.id
            return f'<a href="{url}">{text}</a>'
        else:
            return ref


class ChangelogConvertCommand(BaseChangelogCommand):
    """Convert Slap's old YAML based changelogs to new style TOML changelogs.

    Sometimes the changelog entries in the old style would be suffixed with the
    author's username in the format of <code>@Name</code> or <code>(@Name)</code>, so this command will
    attempt to extract that information to figure out the author of the change.
    """

    name = "changelog convert"
    options = [
        option(
            "--author",
            "-a",
            description="The author to fall back to. If not specified, the current VCS queried for the "
            "author name instead and their email will be used (depending on the normalization of the "
            "repository remote, this will be converted to a username, for example in the case of GitHub).",
            flag=False,
        ),
        option(
            "--directory",
            "-d",
            description="The directory from which to load the old changelogs. Defaults to the same directory that the "
            "new changelogs will be written to.",
            flag=False,
        ),
        option("--dry", description="Do not make changes on disk."),
        option(
            "--fail-fast",
            "x",
            description="If this flag is enabled, exit as soon as an error is encountered with any file.",
        ),
    ]

    CHANGELOG_TYPE_MAPPING_TABLE = {
        "change": "improvement",
        "break": "breaking change",
        "breaking_change": "breaking change",
        "refactor": "hygiene",
    }

    def handle(self) -> int:
        import yaml

        # vcs = self.app.repository.vcs()
        author = self.option("author") or get_default_author(self.app)

        if not author:
            self.line_error("error: missing <opt>--author,-a</opt>", "error")
            return 1

        directory = self.option("directory") or self.manager.directory
        has_failures = False
        for filename in directory.iterdir():
            if has_failures and self.option("fail-fast"):
                break
            if filename.suffix in (".yaml", ".yml"):
                try:
                    self._convert_changelog(author, filename)
                except yaml.error.YAMLError as exc:
                    has_failures = True
                    self.line_error(f'warn: cannot parse "{filename}": {exc}', "warning")
                    continue
                except Exception as exc:
                    has_failures = True
                    self.line_error(f'warn: could not convert "{filename}": {exc}', "warning")
                    if self.io.is_very_verbose():
                        import traceback

                        self.line_error(traceback.format_exc())
                    continue

        return 1 if has_failures else 0

    def _convert_changelog(self, default_author: str, source: Path) -> None:
        import datetime

        import yaml

        data = yaml.safe_load(source.read_text())
        entries = []
        for original_entry in data["changes"]:
            prefix = ""
            component = original_entry["component"]
            if component == "docs":
                change_type = "docs"
            elif component in ("test", "tests"):
                change_type = "tests"
            else:
                change_type = original_entry["type"]
                prefix = f"{component}: " if component != "general" else ""
            author, original_entry["description"] = self._match_author_in_description(original_entry["description"])
            new_entry = self.manager.make_entry(
                change_type=self.CHANGELOG_TYPE_MAPPING_TABLE.get(change_type, change_type),
                description=prefix + original_entry["description"],
                author=author or default_author,
                pr=None,
                issues=original_entry.get("fixes", None) or None,
                component=None,
            )
            entries.append(new_entry)

        if source.stem == "_unreleased":
            dest = self.manager.unreleased()
        else:
            dest = self.manager.version(source.stem)

        changelog = dest.content if dest.exists() else Changelog()
        changelog.release_date = (
            datetime.datetime.strptime(data["release_date"], "%Y-%m-%d").date() if data.get("release_date") else None
        )
        changelog.entries = entries

        if self.option("dry"):
            self.io.write_line(f"<fg=cyan;options=underline># {dest.path}</fg>")
            print(toml_highlight(self.manager.deser.dump(changelog)))
        else:
            dest.save(changelog)

    def _match_author_in_description(self, description: str) -> tuple[str | None, str]:
        """Internal. Tries to find the @Author at the end of a changelog entry description."""

        import re

        match = re.search(r"(.*)\((@[\w\-_ ]+)\)$", description)
        return match.group(2) if match else None, match.group(1).strip() if match else description


class ChangelogCommandPlugin(ApplicationPlugin):
    def load_configuration(self, app: Application) -> ChangelogManager:
        return get_changelog_manager(app.repository, app.main_project())

    def activate(self, app: "Application", config: ChangelogManager) -> None:
        app.cleo.add(ChangelogAddCommand(app, config))
        app.cleo.add(ChangelogDiffUpdatePrCommand(app))
        app.cleo.add(ChangelogDiffAssertCommand(app))
        app.cleo.add(ChangelogFormatCommand(app, config))
        app.cleo.add(ChangelogConvertCommand(app, config))


def get_changelog_manager(repository: Repository, project: Project | None) -> ChangelogManager:
    import databind.json

    config = databind.json.load((project or repository).raw_config().get("changelog", {}), ChangelogConfig)
    if config.enabled is None and project:
        config.enabled = project.is_python_project

    return ChangelogManager(
        directory=(project or repository).directory / config.directory,
        repository_host=repository.host(),
        valid_types=config.valid_types,
        readonly=not config.enabled,
    )
