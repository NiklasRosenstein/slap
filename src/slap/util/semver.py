
import re
from poetry.core.packages.dependency import Dependency  # type: ignore[import]


def parse_dependency(s: str) -> Dependency:
  match = re.match(r'\s*[\w\d\-\_]+', s)
  if match and not s.startswith('git+'):
    return Dependency(match.group(0), s[match.end():])
  return Dependency(s)
