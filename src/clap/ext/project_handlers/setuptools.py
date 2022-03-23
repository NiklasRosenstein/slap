
""" Project handler for projects using the Setuptools build system. """

import typing as t

from clap.project import Dependencies, Package, Project
from clap.ext.project_handlers.default import DefaultProjectHandler


class SetuptoolsProjectHandler(DefaultProjectHandler):

  def __init__(self) -> None:
    self._project: Project | None = None
    self._setup_cfg: t.Dict[str, t.Dict[str, t.Any]] | None = None

  def _get_setup_cfg(self, project: Project) -> t.Dict[str, t.Any]:
    import configparser
    if self._project is None:
      parser = configparser.SafeConfigParser()
      parser.read(project.directory / 'setup.cfg')
      self._setup_cfg = {s: dict(parser.items(s)) for s in parser.sections()}
      self._project = project
    else:
      assert self._project is project
      assert self._setup_cfg is not None
    return self._setup_cfg

  # ProjectHandlerPlugin

  def matches_project(self, project: Project) -> bool:
    if not project.pyproject_toml.exists():
      return False
    build_backend = project.pyproject_toml.get('build-system', {}).get('build-backend')
    return build_backend == 'setuptools.build_meta'

  def get_dist_name(self, project: Project) -> str | None:
    return self._get_setup_cfg(project).get('metadata', {}).get('name')

  def get_readme(self, project: Project) -> str | None:
    cfg = self._get_setup_cfg(project)
    long_description = cfg.get('metadata', {}).get('long_description', '').strip()
    if long_description.startswith('file:'):
      return long_description.partition('file:')[2].partition(',')[0].strip()  # Apparently can be a comma separated list of multiple files
    return None

  def get_packages(self, project: Project) -> list[Package] | None:
    # TODO (@NiklasRosenstein): Handle namespace_packages as well
    options = self._get_setup_cfg(project).get('options', {})
    packages: str | None = options.get('packages')
    if packages is None or packages.strip() == 'find:':
      # Auto detect packages
      # TODO (@NiklasRosenstein): Limit to the package_dir in setup.cfg?
      return super().get_packages(project)
    elif packages.strip() == '':
      return None  # Intentionally no packages
    package_dir = project.directory / options.get('package_dir', '.')
    return [
      Package(p, package_dir / p, package_dir)
      for p in parse_list_semi(packages)
    ]

  def get_dependencies(self, project: Project) -> Dependencies:
    options = self._get_setup_cfg(project).get('options', {})
    return Dependencies(
      parse_list_semi(options.get('install_requires', '')),
      parse_list_semi(options.get('setup_requires', '')) + parse_list_semi(options.get('tests_require', '')),
      {extra: parse_list_semi(value) for extra, value in options.get('extras_require', {}).items()}
    )


def parse_list_semi(val: str) -> t.List[str]:
  """ Parses a string to a list of strinsg according to the `list-semi` specification in the [setuptools docs][1].

  [1]: https://setuptools.pypa.io/en/latest/userguide/declarative_config.html#specifying-values """

  from nr.util.stream import Stream
  return Stream(val.splitlines()).map(lambda v: v.split(';')).concat().map(str.strip).filter(bool).collect()