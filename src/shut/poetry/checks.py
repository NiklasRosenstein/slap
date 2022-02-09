
import typing as t
from pathlib import Path

from nr.util import Optional

from nr.util.fs import get_file_in_directory

from shut.commands.check.api import Check, CheckPlugin
from shut.application import Application


def get_readme_path(app: Application) -> Path | None:
  """ Tries to detect the project readme. If `tool.poetry.readme` is set, that file will be returned. """

  # TODO (@NiklasRosenstein): Support other config styles that specify a readme.

  poetry: dict = app.pyproject.value_or({})
  poetry = poetry.get('tool', {}).get('poetry', {})

  if (readme := poetry.get('readme')) and Path(readme).is_file():
    return Path(readme)

  return get_file_in_directory(Path.cwd(), 'README', ['README.md', 'README.rst', 'README.txt'], case_sensitive=False)


class PoetryChecksPlugin(CheckPlugin):
  """ Check plugin to validate the Poetry configuration and compare it with Shut's expectations. """

  def get_checks(self, app: 'Application') -> t.Iterable[Check]:
    self.app = app
    self.poetry = (app.pyproject.value() if app.pyproject.exists() else {}).get('tool', {}).get('poetry')
    if self.poetry is not None:
      yield self._check_poetry_readme()
      yield self._check_has_homepage_url()
      yield self._check_has_repository_url()
      yield self._check_has_documentation_url()
      yield self._check_poetry_classifiers()
      yield self._check_poetry_license()

  def _check_poetry_readme(self) -> Check:
    check_name = 'readme'
    default_readmes = ['README.md', 'README.rst']
    detected_readme = Optional(get_readme_path(self.app))\
      .map(lambda p: str(p.resolve().relative_to(Path.cwd()))).or_else(None)
    poetry_readme = self.poetry.get('readme')

    if poetry_readme is None and detected_readme in default_readmes:
      return Check(
        check_name,
        Check.Result.OK,
        f'Poetry will autodetect your readme (<b>{detected_readme}</b>)'
      )

    if poetry_readme == detected_readme:
      return Check(
        check_name,
        Check.Result.OK,
        f'Poetry readme is configured correctly (path: <b>{detected_readme}</b>)'
      )

    return Check(
      check_name,
      Check.Result.WARNING,
      f'Poetry readme appears to be misconfigured (detected: <b>{detected_readme}</b>, configured: <b>{poetry_readme}</b>)'
    )

  def _check_has_homepage_url(self) -> Check:
    has_homepage = 'homepage' in self.poetry or 'homepage' in {x.lower() for x in self.poetry.get('urls', {}).keys()}
    return Check(
      'urls:homepage',
      Check.Result.SKIPPED if has_homepage else Check.Result.RECOMMENDATION,
      '<code>tool.poetry.homepage</code> is not configured' if not has_homepage else
        'Configuration detected.'
    )

  def _check_has_repository_url(self) -> Check:
    has_repository = 'repository' in {x.lower() for x in self.poetry.get('urls', {}).keys()}
    return Check(
      'urls:repository',
      Check.Result.SKIPPED if has_repository else Check.Result.RECOMMENDATION,
      '<code>tool.poetry.urls.repository</code> should be configured' if not has_repository else
        'Configuration detected.'
    )

  def _check_has_documentation_url(self) -> Check:
    has_documentation = 'documentation' in {x.lower() for x in self.poetry.get('urls', {}).keys()}
    return Check(
      'urls:documentation',
      Check.Result.SKIPPED if has_documentation else Check.Result.RECOMMENDATION,
      '<code>tool.poetry.urls.documentation</code> should be configured' if not has_documentation else
        'Configuration detected.'
    )

  def _check_poetry_classifiers(self) -> Check:
    return Check('classifiers', Check.Result.SKIPPED, 'Not implemented')

  def _check_poetry_license(self) -> Check:
    return Check('license', Check.Result.SKIPPED, 'Not implemented')
