
import re
import typing as t

from slam.plugins import ReleasePlugin
from slam.project import Project
from slam.release import VersionRef


class InterdependenciesReleasePlugin(ReleasePlugin):
  """ This plugin identifies version references of another project in the set of projects loaded in the application.
  This is relevant in case when Slam is used in a monorepository where all projects share the same version, and bumping
  version numbers should also bump the version number of dependencies between projects in that monorepository.

  You can disable this behaviour by setting the `tool.slam.release.interdependencies` setting to `False` on the
  root project (usually in a `slam.toml` file). """

  def get_version_refs(self, project: Project) -> list[VersionRef]:
    pyproject_file = project.pyproject_toml.path
    if not pyproject_file.exists():
      return []

    enabled = project.repository.raw_config().get('release', {}).get('interdependencies', True)
    if not enabled:
      return []

    other_projects: list[str] = [
      t.cast(str, p.dist_name()) for p in project.repository.projects()
      if p.is_python_project and p is not project and p.dist_name()
    ]

    refs = []

    with pyproject_file.open('r') as fp:
      while True:
        line = fp.readline()
        if not line:
          break

        SELECTOR = r'([\^<>=!~\*]*)(?P<version>\d+\.[\w\d\.\-]+)'

        for name in other_projects:
          # Look for something that looks like a version number. In common TOML formats, that is usually as an entire
          # requirement string or as an assignment.
          expressions = [
            # This first one matches TOML key/value pairs.
            r'([\'"])?' + re.escape(name) + r'\1\s*=\s*([\'"])' + SELECTOR + r'\1',
            re.escape(name) + r'\s*=\s*([\'"])' + SELECTOR + r'\1',
            # This second one matches a TOML string that contains the dependency.
            r'([\'"])' + re.escape(name) + r'(?![^\w\d\_\.\-\ ])\s*' + SELECTOR + r'\1\s*($|,|\]|\})'
          ]

          for expr in expressions:
            for match in re.finditer(expr, line):
              refs.append(VersionRef(
                file=pyproject_file,
                start=fp.tell() -len(line) + match.start('version'),
                end=fp.tell() -len(line) + match.end('version'),
                value=match.group('version'),
                content=line.rstrip(),
              ))

    return refs
