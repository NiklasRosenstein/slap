
import dataclasses
import io
import logging
import re
import typing as t
from pathlib import Path

from databind.core.settings import Alias

from slap.application import Application, Command, argument, option
from slap.plugins import ApplicationPlugin, ChangelogUpdateAutomationPlugin
from slap.changelog import Changelog, ChangelogEntry, ChangelogManager, ManagedChangelog
from slap.project import Project
from slap.repository import Issue, PullRequest, Repository
from slap.util.pygments import toml_highlight

logger = logging.getLogger(__name__)
DEFAULT_VALID_TYPES = [
  'breaking change',
  'deprecation',
  'docs',
  'feature',
  'fix',
  'hygiene',
  'improvement',
  'refactor',
  'tests'
]


def get_default_author(app: Application) -> str | None:
  vcs = app.repository.vcs()
  remote = app.repository.host()
  return (
    remote.get_username(app.repository) if remote else
    vcs.get_author().email if vcs else
    None)


@dataclasses.dataclass
class ChangelogConfig:
  #: Whether the changelog feature is enabled. This acts locally for the current project and not globally.
  #: Particularly useful for monorepos that have multiple subprojects each with their changelog directories
  #: to prevent accidentally creating changelogs in the root directory.
  #:
  #: When not set, it will be considered `True` if the current project is a Python project.
  enabled: bool | None = None

  #: The directory in which changelogs are stored.
  directory: Path = Path('.changelog')

  #: The list of valid types that can be used in changelog entries. The default types are
  #: #DEFAULT_CHANGELOG_TYPES.
  valid_types: t.Annotated[list[str] | None, Alias('valid-types')] = dataclasses.field(
      default_factory=lambda: list(DEFAULT_VALID_TYPES))


class BaseChangelogCommand(Command):

  def __init__(self, app: Application, manager: ChangelogManager) -> None:
    super().__init__()
    self.app = app
    self.manager = manager


class ChangelogAddCommand(BaseChangelogCommand):
  """ Add an entry to the unreleased changelog via the CLI.

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

  Changelog entries can be managed easily using the <info>slap log</info> command.

    <fg=yellow>$</fg> slap log add -t feature -d 'Improvement to `my_package.util`"

  The <fg=green>pr</fg> field is usually set manually after the PR is created or updated
  automatically by a CI action using the <info>slap log update-pr-field</info> command.
  """

  name = "changelog add"

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
        "repository is well supported by Slap, a pull request number may be specified and converted to a full "
        "URL by Slap, otherwise a full URL must be specified.",
      flag=False,
    ),
    option(
      "issue", "i",
      description="An issue related to this changelog. If the remote repository is well supported by Slap, an issue "
        "number may be specified and converted to a full URL by Slap, otherwise a full URL must be specified.",
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

  def handle(self) -> int:
    import databind.json

    if self.manager.readonly:
      self.line_error(f'error: cannot add changelog because the feature must be enabled in the config', 'error')
      return 1

    vcs = self.app.repository.vcs()
    change_type: str | None = self.option("type")
    description: str | None = self.option("description")
    author: str | None = self.option("author") or get_default_author(self.app)
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

    print(toml_highlight(self.manager.deser.dump_entry(entry)))

    if self.option("commit"):
      assert vcs is not None
      commit_message = f'{change_type}: {description}'
      main_project = self.app.main_project()
      relative = main_project.directory.relative_to(self.app.repository.directory) if main_project else Path('.')
      if relative != Path('.'):
        prefix = str(relative).replace("\\", "/").strip("/")
        commit_message = f'{prefix}/: {commit_message}'
      vcs.commit_files([unreleased.path], commit_message)

    return 0


class ChangelogUpdatePrCommand(Command):
  """ Update the <code>pr</code> field of changelog entries in a commit range.

  Updates all changelog entries that were added in a given commit range. This is
  useful to run in CI for a pull request to avoid having to manually update the
  changelog entry after the PR has been created.
  """

  name = "changelog update-pr"
  arguments = [
    argument(
      "base_revision",
      description="The revision ID to look back to to make out which changelog entries have been added since.",
      optional=True,
    ),
    argument(
      "pr",
      description="The reference to the PR that should be inserted into all entries added between the specified "
        "revision and the current version of the unreleased changelog.",
      optional=True,
    )
  ]
  options = [
    option(
      "dry", "d",
      description="Do not actually make changes on disk.",
    ),
    option(
      "overwrite",
      description="Update PR references even if an entry's reference is already set but different.",
    ),
    option(
      "commit", "c",
      description="Commit the changes, if any.",
    ),
    option(
      "push", "p",
      description="Push the changes, if any.",
    ),
    option(
      "name",
      description="Override the <code>user.name</code> Git option (only with <opt>--commit, -c</opt>)",
      flag=False,
    ),
    option(
      "email",
      description="Override the <code>user.email</code> Git option (only with <opt>--commit, -c</opt>).",
      flag=False,
    ),
    option(
      "use",
      description="Use the specified plugin to publish the updated changelogs. Use this in supported CI environments "
        "instead of manually configuring the command-line settings.",
      flag=False,
    ),
    option(
      "list", "l",
      description="List the available plugins you can pass to the <opt>--use</opt> option.",
    )
  ]

  def __init__(self, app: Application):
    super().__init__()
    self.app = app
    self.managers = {project: get_changelog_manager(app.repository, project) for project in app.repository.projects()}

  def handle(self) -> int:
    from nr.util.plugins import iter_entrypoints, load_entrypoint

    if not self._validate_arguments():
      return 1

    if self.option("list"):
      for ep in iter_entrypoints(ChangelogUpdateAutomationPlugin.ENTRYPOINT ):
        self.line(f'  • {ep.name}')
      return 0

    automation_plugin: ChangelogUpdateAutomationPlugin | None = None
    if plugin_name := self.option("use"):
      logger.info('Loading changelog update automation plugin <subj>%s</subj>', plugin_name)
      automation_plugin = load_entrypoint(ChangelogUpdateAutomationPlugin, plugin_name)()  # type: ignore[misc]
      automation_plugin.io = self.io
      automation_plugin.initialize()
      base_revision: str = automation_plugin.get_base_ref()
    else:
      base_revision = self.argument("base_revision")
    assert base_revision

    changelogs: list[tuple[ManagedChangelog, ChangelogManager]] = []
    for _, manager in self.managers.items():
      unreleased = manager.unreleased()
      if unreleased.exists():
        changelogs.append((unreleased, manager))

    if not changelogs:
      self.line('no entries to update', 'info')
      return 0

    if not (pr := self.argument("pr")):
      assert automation_plugin
      pr = automation_plugin.get_pr()

    host = self.app.repository.host()
    if host:
      try:
        pr = host.get_pull_request_by_reference(pr).url
      except ValueError as exc:
        self.line_error(f'error: {exc}', 'error')
        return 1

    num_updates = 0
    for changelog, manager in changelogs:

      prev_contents = self._vcs.get_file_contents(changelog.path, base_revision)
      if prev_contents is None:
        prev_entry_ids = set[str]()
      else:
        prev_changelog = manager.deser.load(io.StringIO(prev_contents.decode('utf8')), f'{base_revision}:{changelog.path}')
        prev_entry_ids = {e.id for e in prev_changelog.entries}

      new_entry_ids = {e.id for e in changelog.content.entries if e.pr != pr} - prev_entry_ids
      entries_to_update = [
        e for e in changelog.content.entries
        if e.id in new_entry_ids and (not e.pr or self.option("overwrite"))
      ]
      if not entries_to_update:
        continue

      self.line(
        f'update <info>{changelog.path.relative_to(Path.cwd())}</info> '
        f'({len(entries_to_update)} reference{"s" if len(new_entry_ids) != 1 else ""})')

      num_updates += len(entries_to_update)
      for entry in entries_to_update:
        entry.pr = pr

      if not self.option("dry"):
        changelog.save(None)

    if not num_updates:
      self.line('no entries to update', 'info')
      return 0

    if self.option("dry"):
      return 0

    changed_files = [changelog.path for changelog, _ in changelogs]

    if self.option("commit"):
      assert not self.automation_plugin
      self._vcs.commit_files(
        changed_files,
        f'Updated {num_updates} PR reference{"" if num_updates == 0 else "s"}.',
        push=self._remote,
        name=self.option("name"),
        email=self.option("email"),
      )

    if automation_plugin:
      automation_plugin.publish_changes(changed_files)

    return 0

  def _validate_arguments(self) -> bool:
    if self.option("list"):
      if used_option := next((o.name for o in self.options if o.name != "list" and self.option(o.name)), None):
        self.line_error(f'error: <opt>--{used_option}</opt> cannot be used with <opt>--list</opt>', 'error')
        return False

    elif self.option("use"):
      if used_option := next((o.name for o in self.options if o.name != "use" and self.option(o.name)), None):
        self.line_error(f'error: <opt>--{used_option}</opt> cannot be used with <opt>--use</opt>', 'error')
        return False

    else:
      for arg in ("base_revision", "pr"):
        if not self.argument(arg):
          self.line_error(f'error: missing argument <opt>{arg}</opt>', 'error')
          return False

    if self.option("push") and not self.option("commit"):
      self.line_error(
        f'error: <opt>--push, -p</opt> can only be used in combination with <opt>--commit, -c</opt>',
        'error')
      return False

    vcs = self.app.repository.vcs()
    if not vcs:
      self.line_error('error: VCS is not configured or could not be detected', 'error')
      return False
    self._vcs = vcs

    if self.option("push"):
      self._remote = next((r for r in self._vcs.get_remotes() if r.default), None)
    else:
      self._remote = None

    for opt in ('email', 'name'):
      if self.option(opt) and not self.option("commit"):
        self.line_error(f'error: <opt>--{opt}</opt> is not valid without <opt>--commit, -c</opt>', 'error')
        return False

    return True


class ChangelogFormatCommand(BaseChangelogCommand):
  """ Format the changelog in the terminal or in Markdown format. """

  name = "changelog format"
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
      description = entry.description
      description = re.sub(r'(?!<\\)`([^`]+)`', r'<fg=dark_gray>\1</fg>', description)
      self.line(f'  <fg=cyan;options=italic>{entry.type}</fg> — {description} (<fg=yellow>{entry.author}</fg>)')

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
    if self.manager.repository_host:
      try:
        if type == 'pr':
          item: Issue | PullRequest = self.manager.repository_host.get_pull_request_by_reference(ref)
        else:
          item = self.manager.repository_host.get_issue_by_reference(ref)
      except ValueError as exc:
        self.line_error(f'warning: {exc}', 'error')
        url = ref
        text = 'Link'
      else:
        url, text = item.url, item.id
    return f'<a href="{url}">{text}</a>'


class ChangelogConvertCommand(BaseChangelogCommand):
  """ Convert Slap's old YAML based changelogs to new style TOML changelogs.

  Sometimes the changelog entries in the old style would be suffixed with the
  author's username in the format of <code>@Name</code> or <code>(@Name)</code>, so this command will
  attempt to extract that information to figure out the author of the change.
  """

  name = "changelog convert"
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
    'break': 'breaking change',
    'breaking_change': 'breaking change',
    'refactor': 'hygiene',
  }

  def handle(self) -> int:
    import yaml

    vcs = self.app.repository.vcs()
    author = self.option("author") or get_default_author(self.app)

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
          self.line_error(f'warn: cannot parse "{filename}": {exc}', 'warning')
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
    changelog.release_date = datetime.datetime.strptime(data['release_date'], '%Y-%m-%d').date() if data.get('release_date') else None
    changelog.entries = entries

    if self.option("dry"):
      self.io.write_line(f'<fg=cyan;options=underline># {dest.path}</fg>')
      print(toml_highlight(self.manager.deser.dump(changelog)))
    else:
      dest.save(changelog)

  def _match_author_in_description(self, description: str) -> tuple[str | None, str]:
    """ Internal. Tries to find the @Author at the end of a changelog entry description. """

    import re
    match = re.search(r'(.*)\((@[\w\-_ ]+)\)$', description)
    return match.group(2) if match else None, match.group(1).strip() if match else description


class ChangelogCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> ChangelogManager:
    return get_changelog_manager(app.repository, app.main_project())

  def activate(self, app: 'Application', config: ChangelogManager) -> None:
    app.cleo.add(ChangelogAddCommand(app, config))
    app.cleo.add(ChangelogUpdatePrCommand(app))
    app.cleo.add(ChangelogFormatCommand(app, config))
    app.cleo.add(ChangelogConvertCommand(app, config))


def get_changelog_manager(repository: Repository, project: Project | None) -> ChangelogManager:
  import databind.json
  config = databind.json.load((project or repository).raw_config().get('changelog', {}), ChangelogConfig)
  if config.enabled is None and project:
    config.enabled = project.is_python_project

  return ChangelogManager(
    directory=(project or repository).directory / config.directory,
    repository_host=repository.host(),
    valid_types=config.valid_types,
    readonly=not config.enabled,
  )
