
import io
import typing as t
from pathlib import Path

from slam.application import Application, ApplicationPlugin, Command, argument, option
from slam.changelog.model import Changelog
from slam.changelog.manager import ChangelogManager, DEFAULT_VALID_TYPES, ManagedChangelog
from slam.commands.check.api import CheckPlugin
from slam.commands.log.config import get_changelog_manager
from slam.commands.release.api import ReleasePlugin
from slam.util.pygments import toml_highlight
from .checks import ChangelogConsistencyCheck
from .release_plugin import RenameChangelogOnReleasePlugin


class LogAddCommand(Command):
  """
  Add an entry to the unreleased changelog via the CLI.

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

  Changelog entries can be managed easily using the <info>slam log</info> command.

    <fg=yellow>$</fg> slam log add -t feature -d 'Improvement to `my_package.util`"

  The <fg=green>pr</fg> field is usually set manually after the PR is created or updated
  automatically by a CI action using the <info>slam log update-pr-field</info> command.
  """

  name = "log add"

  options = [
    option(
      "type", "t",
      description=f"The type of the changelog. Unless configured differently, one of {', '.join(DEFAULT_VALID_TYPES)}",
      flag=False,
    ),
    option(
      "description", "d",
      description="A Markdown formatted description of the changelog entry.",
      flag=False,
    ),
    option(
      "author", "a",
      description="Your username or email address. By default, this will be your configured Git name and email address.",
      flag=False,
    ),
    option(
      "pr", None,
      description="The pull request that the change is introduced to the main branch with. This is not usually "
        "known at the time the changelog entry is created, so this option is not often used. If the remote "
        "repository is well supported by Slam, a pull request number may be specified and converted to a full "
        "URL by Slam, otherwise a full URL must be specified.",
      flag=False,
    ),
    option(
      "issue", "i",
      description="An issue related to this changelog. If the remote repository is well supported by Slam, an issue "
        "number may be specified and converted to a full URL by Slam, otherwise a full URL must be specified.",
      flag=False,
      multiple=True,
    ),
    option(
      "commit", "c",
      description="Commit the currently staged changes in the VCS as well as the updated changelog file to disk. The "
        "commit message is a concatenation of the <opt>--type, -t</opt> and <opt>--description, -d</opt>, as well as "
        "the directory relative to the VCS toplevel if the changelog is created not in the toplevel directory of the "
        "repository."
    ),
  ]

  def __init__(self, app: Application, manager: ChangelogManager) -> None:
    super().__init__()
    self.app = app
    self.manager = manager

  def handle(self) -> int:
    import databind.json

    vcs = self.app.get_vcs()
    change_type: str | None = self.option("type")
    description: str | None = self.option("description")
    author: str | None = self.option("author") or (vcs.get_author().email if vcs else None)
    pr: str | None = self.option("pr")
    issues: list[str] | None = self.option("issue")

    if not vcs and self.option("commit"):
      self.line_error('error: no VCS detected, but <opt>--commit, -c</opt> was used', 'error')
      return 1

    if not change_type:
      self.line_error('error: missing <opt>--type,-t</opt>', 'error')
      return 1
    if not description:
      self.line_error('error: missing <opt>--description,-d</opt>', 'error')
      return 1
    if not author:
      self.line_error('error: missing <opt>--author,-a</opt>', 'error')
      return 1

    entry = self.manager.make_entry(change_type, description, author, pr, issues)
    unreleased = self.manager.unreleased()
    changelog = unreleased.content if unreleased.exists() else Changelog()
    changelog.entries.append(entry)
    unreleased.save(changelog)

    print(toml_highlight(t.cast(dict, databind.json.dump(entry))))

    if self.option("commit"):
      assert vcs is not None
      commit_message = f'{change_type}: {description}'
      toplevel = vcs.get_toplevel()
      relative = self.app.project_directory.relative_to(toplevel)
      if relative != Path('.'):
        prefix = str(relative).replace("\\", "/").strip("/")
        commit_message = f'{prefix}/: {commit_message}'
      vcs.commit_files([unreleased.path], commit_message)

    return 0


class LogPrUpdateCommand(Command):
  """
  Update the <u>pr</u> field of changelog entries in a commit range.

  Updates all changelog entries that were added in a given commit range. This is
  useful to run in CI for a pull request to avoid having to manually update the
  changelog entry after the PR has been created.
  """

  name = "log update-pr"
  arguments = [
    argument(
      "base_revision",
      description="The revision ID to look back to to make out which changelog entries have been added since."
    ),
    argument(
      "pr",
      description="The reference to the PR that should be inserted into all entries added between the specified "
        "revision and the current version of the unreleased changelog.",
    )
  ]
  options = [
    option(
      "commit", "c",
      description="Commit the changes, if any.",
    ),
    option(
      "push", "p",
      description="Push the changes, if any.",
    )
  ]

  def __init__(self, app: Application, manager: ChangelogManager):
    super().__init__()
    self.app = app
    self.manager = manager

  def handle(self) -> int:
    if not self._validate_arguments():
      return 1

    try:
      pr = self.manager.validator.normalize_pr_reference(self.argument("pr"))
    except ValueError as exc:
      self.line_error(f'error: {exc}', 'error')
      return 1

    unreleased = self.manager.unreleased()
    if not unreleased.exists():
      self.line('no entries to update', 'info')
      return 0

    rev = self.argument("base_revision")
    prev_contents = self._vcs.get_file_contents(unreleased.path, rev)
    if prev_contents is None:
      prev_entry_ids = set[str]()
    else:
      prev_changelog = self.manager.deser.load(io.StringIO(prev_contents.decode('utf8')), f'{rev}:{unreleased.path}')
      prev_entry_ids = {e.id for e in prev_changelog.entries}

    new_entry_ids = {e.id for e in unreleased.content.entries} - prev_entry_ids
    if not new_entry_ids:
      self.line('no entries to update', 'info')
      return 0

    self.line(f'Updating PR reference in {len(new_entry_ids)} {"entry" if len(new_entry_ids) == 1 else "entries"}', 'comment')
    for entry in unreleased.content.entries:
      if entry.id in new_entry_ids:
        entry.pr = pr
    unreleased.save(None)

    if self.option("commit"):
      self._vcs.commit_files([unreleased.path], 'Updated PR references.', push=self._remote)

    return 0

  def _validate_arguments(self) -> bool:
    if self.option("push") and not self.option("commit"):
      self.line_error(
        f'error: <opt>--push, -p</opt> can only be used in combination with <opt>--commit, -c</opt>',
        'error')
      return False

    vcs = self.app.get_vcs()
    if not vcs:
      self.line_error('error: VCS is not configured or could not be detected', 'error')
      return False
    self._vcs = vcs

    if self.option("push"):
      self._remote = next((r for r in self._vcs.get_remotes() if r.default), None)
    else:
      self._remote = None

    return True


class LogFormatComand(Command):
  """
  Format the changelog in the terminal or in Markdown format.
  """

  name = "log format"
  options = [
    option(
      "markdown", "m",
      description="Render the changelog in Markdown format.",
    ),
    option(
      "all", "a",
      description="Render all changelogs in reverse chronological order.",
    ),
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

    if self.option("all"):
      changelogs = self.manager.all()
    elif (version := self.argument("version")):
      changelogs = [self.manager.version(version)]
      if not changelogs[0].exists():
        self.line_error(f'error: Changelog for <opt>version</opt> "{version}" does not exist.', 'error')
        return 1
    else:
      changelogs = [self.manager.unreleased()]

    for changelog in changelogs:
      if self.option("markdown"):
        self._render_markdown(changelog)
      else:
        self._render_terminal(changelog)
      self.line('')

    return 0

  def _validate_arguments(self) -> bool:
    if self.option("all") and self.argument("version"):
      self.line_error(f'error: <opt>--all, -a</opt> is incompatible with <opt>version</opt> argument', 'error')
      return False
    return True

  def _render_terminal(self, changelog: ManagedChangelog) -> None:
    if changelog.version:
      assert changelog.content.release_date
      self.line(f'<b>{changelog.version}</b> (<u>{changelog.content.release_date}</u>)')
    else:
      self.line(f'<b>{changelog.version or "Unreleased"}</b>')
      if not changelog.exists():
        return

    for entry in changelog.content.entries:
      self.line(f'  <fg=cyan;options=italic>{entry.type}</fg> — {entry.description} (<fg=yellow>{entry.author}</fg>)')

  def _render_markdown(self, changelog: ManagedChangelog) -> None:
    if changelog.version:
      assert changelog.content.release_date
      print(f'## {changelog.version} ({changelog.content.release_date})')
    else:
      print(f'## Unreleased')
      if not changelog.exists():
        return

    print()
    print('<table><tr><th>Type</th><th>Description</th><th>PR</th><th>Issues</th><th>Author</th></tr>')
    for entry in changelog.content.entries:
      pr_link = self._html_anchor('pr', entry.pr) if entry.pr else ''
      issues = ', '.join(self._html_anchor('issue', issue) for issue in entry.issues) if entry.issues else ''
      print(f'  <tr><td>{entry.type.capitalize()}</td><td>\n\n{entry.description}</td>'
        f'<td>{pr_link}</td><td>{issues}</td><td>{", ".join(entry.get_authors())}</td></tr>')
    print('</table>')

  def _html_anchor(self, type: t.Literal['pr', 'issue'], ref: str) -> str:
    if type == 'pr':
      shortform = self.manager.validator.pr_shortform(ref)
    else:
      shortform = self.manager.validator.issue_shortform(ref)
    if shortform is None:
      shortform = 'Link'
    return f'<a href="{ref}">{shortform}</a>'


class LogConvertCommand(Command):
  """
  Convert Slam's old YAML based changelogs to new style TOML changelogs.

  Sometimes the changelog entries in the old style would be suffixed with the
  author's username in the format of <code>@Name</code> or <code>(@Name)</code>, so this command will
  attempt to extract that information to figure out the author of the change.
  """

  name = "log convert"
  options = [
    option(
      "author", "a",
      description="The author to fall back to. If not specified, the current VCS queried for the "
        "author name instead and their email will be used (depending on the normalization of the "
        "repository remote, this will be converted to a username, for example in the case of GitHub).",
      flag=False,
    ),
    option(
      "directory", "d",
      description="The directory from which to load the old changelogs. Defaults to the same directory that the "
        "new changelogs will be written to.",
      flag=False,
    ),
    option(
      "dry",
      description="Do not make changes on disk."
    ),
    option(
      "fail-fast", "x",
      description="If this flag is enabled, exit as soon as an error is encountered with any file.",
    ),
  ]

  CHANGELOG_TYPE_MAPPING_TABLE = {
    'change': 'improvement',
    'breaking_change': 'breaking change',
    'refactor': 'hygiene',
  }

  def __init__(self, app: Application, manager: ChangelogManager) -> None:
    super().__init__()
    self.app = app
    self.manager = manager

  def handle(self) -> int:
    import yaml

    vcs = self.app.get_vcs()
    author = self.option("author") or (vcs.get_author().email if vcs else None)

    if not author:
      self.line_error('error: missing <opt>--author,-a</opt>', 'error')
      return 1

    directory = self.option("directory") or self.manager.directory
    has_failures = False
    for filename in directory.iterdir():
      if has_failures and self.option("fail-fast"):
        break
      if filename.suffix in ('.yaml', '.yml'):
        try:
          self._convert_changelog(author, filename)
        except yaml.error.YAMLError as exc:
          has_failures = True
          self.line_error(f'warn: cannot parse "{filename}"', 'warning')
          continue
        except Exception as exc:
          has_failures = True
          self.line_error(f'warn: could not convert "{filename}": {exc}', 'warning')
          if self.io.is_very_verbose:
            import traceback
            self.line_error(traceback.format_exc())
          continue

    return 1 if has_failures else 0

  def _convert_changelog(self, default_author: str, source: Path) -> None:
    import datetime
    import databind.json
    import yaml

    data = yaml.safe_load(source.read_text())
    entries = []
    for original_entry in data['changes']:
      prefix = ''
      component = original_entry['component']
      if component == 'docs':
        change_type = 'docs'
      elif component in ('test', 'tests'):
        change_type = 'tests'
      else:
        change_type = original_entry['type']
        prefix = f'{component}: ' if component != 'general' else ''
      author, original_entry['description'] = self._match_author_in_description(original_entry['description'])
      new_entry = self.manager.make_entry(
        change_type=self.CHANGELOG_TYPE_MAPPING_TABLE.get(change_type, change_type),
        description=prefix + original_entry['description'],
        author=author or default_author,
        pr=None,
        issues=original_entry.get('fixes', None) or None,
      )
      entries.append(new_entry)

    if source.stem == '_unreleased':
      dest = self.manager.unreleased()
    else:
      dest = self.manager.version(source.stem)

    changelog = dest.content if dest.exists() else Changelog()
    changelog.release_date = datetime.datetime.strptime(data['release_date'], '%Y-%m-%d').date()
    changelog.entries = entries

    if self.option("dry"):
      self.io.write_line(f'<fg=cyan;options=underline># {dest.path}</fg>')
      print(toml_highlight(t.cast(dict, databind.json.dump(changelog))))
    else:
      dest.save(changelog)

  def _match_author_in_description(self, description: str) -> tuple[str | None, str]:
    """ Internal. Tries to find the @Author at the end of a changelog entry description. """

    import re
    match = re.search(r'(.*)\((@[\w\-_ ]+)\)$', description)
    return match.group(2) if match else None, match.group(1).strip() if match else description


class LogCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> ChangelogManager:
    return get_changelog_manager(app)

  def activate(self, app: 'Application', manager: ChangelogManager) -> None:
    app.plugins.register(CheckPlugin, 'log', ChangelogConsistencyCheck(manager))
    app.plugins.register(ReleasePlugin, 'log', RenameChangelogOnReleasePlugin(manager))
    app.cleo.add(LogAddCommand(app, manager))
    app.cleo.add(LogPrUpdateCommand(app, manager))
    app.cleo.add(LogFormatComand(manager))
    app.cleo.add(LogConvertCommand(app, manager))
