
import typing as t

from shut.application import Application
from shut.commands.check.api import Check, CheckPlugin
from .builtin import SourceCodeVersionMatcherPlugin


class ReleaseChecksPlugin(CheckPlugin):

  # TODO (@NiklasRosenstein): Check if the versions are consistent

  def get_checks(self, app: 'Application') -> t.Iterable[Check]:
    from cleo.io.null_io import NullIO  # type: ignore[import]

    check_name = 'version'
    packages = app.get_packages()
    if not packages:
      return [Check(check_name, Check.Result.WARNING, 'No packages detected')]

    matcher = SourceCodeVersionMatcherPlugin(packages)
    version_refs = matcher.get_version_refs(NullIO())
    packages_without_version = {p.name for p in packages}
    for ref in version_refs:
      for package in packages:
        if ref.file.is_relative_to(package.path):
          packages_without_version.discard(package.name)

    return [
      Check(
        check_name,
        Check.ERROR if packages_without_version else Check.OK,
        (f'The following packages have no <b>__version__</b>: <b>{", ".join(packages_without_version)}</b>')
          if packages_without_version else
          f'Found <b>__version__</b> in <b>{", ".join(x.name for x in packages)}</b>')
    ]
