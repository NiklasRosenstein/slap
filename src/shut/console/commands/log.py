
import dataclasses
import typing as t

from databind.core.annotations import alias

from shut.changelog.manager import ChangelogManager
from shut.console.command import Command, argument, option
from shut.console.application import Application
from shut.plugins.application_plugin import ApplicationPlugin

DEFAULT_CHANGELOG_TYPES = ['breaking change', 'docs', 'feature', 'fix', 'hygiene', 'improvement']


@dataclasses.dataclass
class LogConfig:
  directory: str = '.changelog'
  valid_types: t.Annotated[list[str], alias('valid-types')] = dataclasses.field(default_factory=lambda: list(DEFAULT_CHANGELOG_TYPES))



def get_log_config(app: Application) -> LogConfig:
  import databind.json
  return databind.json.load(app.project_config.extras.get('log', {}), LogConfig)


class BaseCommand(Command):

  def __init__(self, app: Application):
      super().__init__()
      self._app = app

  @property
  def config(self) -> LogConfig:
    return get_log_config(self._app)


class LogAddCommand(BaseCommand):

  name = "log add"
  description = "Add an entry to the unreleased changelog."
  help = """
    The <info>shut log add</info> command allows you to add structured changelog via the CLI.

    A changelog is a TOML file, usually in the <fg=cyan>.changelog/</fg> directory, named with the version number
    it refers to and containing changelog entries. Changes that are currently not released in a version are stored
    in a file called <fg=cyan>_unreleased.toml</fg>.

    Changelog entries contain at least one author, a type (e.g. whether the entry describes a feature, enhancement,
    bug fix, etc.) and optionally a subject (e.g. whether the change is related to docs or a particular component of
    the code), a Markdown description, possibly a link to a pull request with which the change was introduced and
    links to issues that the changelog addresses.

    <b>Example</b>

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

        <fg=cyan>$ shut log add -t feature -d 'Improvement to `my_package.util`"</fg>

    The <fg=green>pr</fg> field is usually set manually after the PR is created or updated automatically by a CI
    action using the <info>shut log update-pr-field</info> command.
  """

  options = [
    option(
      "type", "t",
      f"The type of the changelog. Unless configured differently, one of {', '.join(DEFAULT_CHANGELOG_TYPES)}",
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
      "fixes", "f",
      "An issue that the change fixes. If the remote repository is well supported by Shut, an issue number may "
        "be specified and converted to a full URL by Shut, otherwise a full URL must be specified.",
      flag=False,
      multiple=True,
    )
  ]

  def handle(self) -> int:
    change_type: str | None = self.option("type")
    description: str | None = self.option("description")
    author: str | None = self.option("author")
    pr: str | None = self.option("pr")
    fixes: list[str] | None = self.option("fixes")

    if not change_type:
      self.line_error('error: missing --type,-t', 'error')
      return 1
    if not description:
      self.line_error('error: missing --description,-d', 'error')
      return 1
    if not author:
      self.line_error('error: missing --author,-a', 'error')
      return 1

    config = self.config

    if change_type not in config.valid_types:
      self.line_error(f'error: bad changelog type: <b>{change_type}</b>', 'error')
      return 1

    print(config)



class LogPrUpdateCommand(BaseCommand):

  name = "log pr update"
  description = "Update the <fg=green>pr</fg> field of changelog entries in a commit range."
  help = """
    The <info>shut log pr update</info> updates all changelog entries that were added in a given commit range. This
    is useful to run in CI for a pull request to avoid having to manually update the changelog entry after the PR
    has been created.
  """


class LogFormatComand(BaseCommand):

  name = "log format"
  description = "Format the changelog."
  help = """
    The <info>shut log format</info> command formats one or all changelogs in a more readable format. The
    supported formats are optimized for the <b>terminal</b> and for <b>Markdown</b>.
  """


class LogPlugin(ApplicationPlugin):

  def activate(self, app: 'Application') -> None:
    app.cleo.add(LogAddCommand(app))
    app.cleo.add(LogPrUpdateCommand(app))
    app.cleo.add(LogFormatComand(app))
