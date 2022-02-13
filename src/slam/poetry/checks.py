
import typing as t
from pathlib import Path

import requests
from nr.util import Optional
from nr.util.fs import get_file_in_directory

from slam.application import Application
from slam.commands.check.api import Check, CheckPlugin
from slam.util.external.pypi_classifiers import get_classifiers


def get_readme_path(app: Application) -> Path | None:
  """ Tries to detect the project readme. If `tool.poetry.readme` is set, that file will be returned. """

  # TODO (@NiklasRosenstein): Support other config styles that specify a readme.

  poetry: dict = app.pyproject.value_or({})
  poetry = poetry.get('tool', {}).get('poetry', {})

  if (readme := poetry.get('readme')) and Path(readme).is_file():
    return Path(readme)

  return get_file_in_directory(Path.cwd(), 'README', ['README.md', 'README.rst', 'README.txt'], case_sensitive=False)


class PoetryChecksPlugin(CheckPlugin):
  """ Check plugin to validate the Poetry configuration and compare it with Slam's expectations. """

  def get_checks(self, app: 'Application') -> t.Iterable[Check]:
    self.app = app
    self.poetry = (app.pyproject.value() if app.pyproject.exists() else {}).get('tool', {}).get('poetry')
    if self.poetry is not None:
      yield self._check_poetry_readme()
      yield self._check_urls()
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

  def _check_urls(self) -> Check:
    has_homepage = 'homepage' in self.poetry or 'homepage' in {x.lower() for x in self.poetry.get('urls', {}).keys()}
    has_repository = 'repository' in {x.lower() for x in self.poetry.get('urls', {}).keys()}
    has_documentation = 'documentation' in {x.lower() for x in self.poetry.get('urls', {}).keys()}
    has_bug_tracker = 'bug tracker' in {x.lower() for x in self.poetry.get('urls', {}).keys()}

    if has_homepage and has_repository and has_documentation and has_bug_tracker:
      result = Check.OK
      message = 'Your project URLs are in top condition.'
    else:
      missing = [k for k, v in {
        'Homepage': has_homepage,
        'Repository': has_repository,
        'Documentation': has_documentation,
        'Bug Tracker': has_bug_tracker
      }.items() if not v]
      result = Check.RECOMMENDATION if has_homepage else Check.WARNING
      message = 'Please configure the following URLs: ' + ', '.join(f'<s>"{k}"</s>' for k in missing)

    return Check('urls', result, message)

  def _check_poetry_classifiers(self) -> Check:
    # TODO: Check for recommended classifier topics (Development State, Environment, Programming Language, Topic, Typing, etc.)
    classifiers = self.poetry.get('classifiers')  # TODO: Support classifiers in [project]
    details = None
    if not classifiers:
      result = Check.RECOMMENDATION
      message = 'Please configure classifiers.'
    else:
      try:
        good_classifiers = get_classifiers()
      except requests.RequestException as exc:
        result = Check.WARNING
        message = f'Could not validate classifiers because list could not be fetched ({exc})'
      else:
        bad_classifiers = set(classifiers) - set(good_classifiers)
        if bad_classifiers:
          result = Check.ERROR
          message = f'Found bad classifiers: ' + ','.join(f'<s>"{c}"</s>' for c in bad_classifiers)
        else:
          result = Check.OK
          message = 'All classifiers are valid.'
    return Check('classifiers', result, message, details)

  def _check_poetry_license(self) -> Check:
    from slam.util.external.licenses import get_spdx_licenses
    license = self.poetry.get('license')
    if not license:
      result = Check.ERROR
      message = 'Missing license'
    else:
      if license not in get_spdx_licenses():
        result = Check.WARNING
        message = f'License <s>"{license}"</s> is not a known SPDX license identifier.'
      else:
        result = Check.OK
        message = f'License <s>"{license}"</s> is a valid SPDX identifier.'
    return Check('license', result, message)
