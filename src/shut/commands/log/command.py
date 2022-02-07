
import typing as t

from shut.application import Application, ApplicationPlugin, Command, argument, option
from shut.changelog.model import Changelog
from shut.changelog.changelog_manager import ChangelogManager, DEFAULT_VALID_TYPES, ManagedChangelog
from shut.commands.check.api import CheckPlugin
from shut.commands.log.config import get_changelog_manager
from .checks import ChangelogConsistencyCheck


class LogAddCommand(Command):
  """
  Allows you to add structured changelog via the CLI.

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

  Changelog entries can be managed easily using the <info>shut log</info> command.

    <fg=yellow>$</fg> shut log add -t feature -d 'Improvement to `my_package.util`"

  The <fg=green>pr</fg> field is usually set manually after the PR is created or updated
  automatically by a CI action using the <info>shut log update-pr-field</info> command.
  """

  name = "log add"

  options = [
    option(
      "type", "t",
      f"The type of the changelog. Unless configured differently, one of {', '.join(DEFAULT_VALID_TYPES)}",
      flag=False,
    ),
    option(
      "description", "d",
      "A Markdown formatted description of the changelog entry.",
      flag=False,
    ),
    option(
      "author", "a",
      "Your username or email address. By default, this will be your configured Git name and email address.",
      flag=False,
    ),
    option(
      "pr", None,
      "The pull request that the change is introduced to the main branch with. This is not usually "
        "known at the time the changelog entry is created, so this option is not often used. If the remote "
        "repository is well supported by Shut, a pull request number may be specified and converted to a full "
        "URL by Shut, otherwise a full URL must be specified.",
      flag=False,
    ),
    option(
      "issue", "i",
      "An issue related to this chagnelog. If the remote repository is well supported by Shut, an issue number may "
        "be specified and converted to a full URL by Shut, otherwise a full URL must be specified.",
      flag=False,
      multiple=True,
    )
  ]

  def __init__(self, manager: ChangelogManager) -> None:
    super().__init__()
    self.manager = manager

  def handle(self) -> int:
    change_type: str | None = self.option("type")
    description: str | None = self.option("description")
    author: str | None = self.option("author")
    pr: str | None = self.option("pr")
    issues: list[str] | None = self.option("issue")

    if not change_type:
      self.line_error('error: missing --type,-t', 'error')
      return 1
    if not description:
      self.line_error('error: missing --description,-d', 'error')
      return 1

    try:
      entry = self.manager.make_entry(change_type, description, author, pr, issues)
    except ValueError as exc:
      if 'author' in str(exc):
        self.line_error('error: author could not be automatically detected, specify <opt>--author, -a</opt>', 'error')
        return 1
      raise

    unreleased = self.manager.unreleased()
    changelog = unreleased.content if unreleased.exists() else Changelog()
    changelog.entries.append(entry)
    unreleased.save(changelog)

    import databind.json
    import tomli_w
    import pygments, pygments.lexers, pygments.formatters

    highlighted = pygments.highlight(
      tomli_w.dumps(t.cast(dict, databind.json.dump(entry))),
      pygments.lexers.get_lexer_by_name('toml'),
      pygments.formatters.get_formatter_by_name('terminal')
    )
    print(highlighted)

    return 0


class LogPrUpdateCommand(Command):
  """
  Update the <u>pr</u> field of changelog entries in a commit range.

  Updates all changelog entries that were added in a given commit range. This is
  useful to run in CI for a pull request to avoid having to manually update the
  changelog entry after the PR has been created.
  """

  name = "log pr update"


class LogFormatComand(Command):
  """
  Format the changelog in the terminal or in Markdown format.
  """

  name = "log format"
  options = [
    option("markdown", "m", "Render the changelog in Markdown format."),
    option("all", "a", "Render all changelogs in reverse chronological order."),
  ]
  arguments = [
    argument("version", "The changelog version to format.", optional=True),
  ]

  def __init__(self, manager: ChangelogManager):
    super().__init__()
    self.manager = manager

  def handle(self) -> int:
    if not self._validate_arguments():
      return 1

    if (version := self.argument("version")):
      changelog = self.manager.version(version)
      if not changelog.exists():
        self.line_error(f'error: Changelog for <opt>version</opt> "{version}" does not exist.', 'error')
        return 1
    else:
      changelog = self.manager.unreleased()

    if self.option("markdown"):
      self._render_markdown(changelog)
    else:
      self._render_terminal(changelog)

    return 0

  def _validate_arguments(self) -> bool:
    if self.option("all") and self.argument("version"):
      self.line_error(f'error: <opt>--all, -a</opt> is incompatible with <opt>version</opt> argument', 'error')
      return False
    return True

  def _render_terminal(self, changelog: ManagedChangelog) -> None:
    if changelog.version:
      self.line(f'<b>{changelog.version}</b> (<u>{changelog.content.release_date}</u>)')
    else:
      self.line(f'<b>{changelog.version or "Unreleased"}</b>')
      if not changelog.exists():
        return

    for entry in changelog.content.entries:
      self.line(f'  <fg=cyan;options=italic>{entry.type}</fg> — {entry.description} (<fg=yellow>{entry.author}</fg>)')

  def _render_markdown(self, changelog: ManagedChangelog) -> None:
    pass


class LogCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> ChangelogManager:
    return get_changelog_manager(app)

  def activate(self, app: 'Application', manager: ChangelogManager) -> None:
    app.plugins.register(CheckPlugin, 'log', ChangelogConsistencyCheck(manager))
    app.cleo.add(LogAddCommand(manager))
    app.cleo.add(LogPrUpdateCommand())
    app.cleo.add(LogFormatComand(manager))
