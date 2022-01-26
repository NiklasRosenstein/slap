
from pathlib import Path


def get_file_in_directory(
  directory: Path,
  prefix: str,
  preferred: list[str],
  case_sensitive: bool = True,
) -> Path | None:
  """ Returns a file in *directory* that is either in the *preferred* list or starts with specified *prefix*. """

  if not case_sensitive:
    preferred = [x.lower() for x in preferred]

  choices = []
  for path in sorted(directory.iterdir()):
    if (case_sensitive and path.name in preferred) or (not case_sensitive and path.name.lower() in preferred):
      return path
    if path.name.startswith(prefix):
      choices.append(path)
  else:
    if choices:
      return choices[0]

  return None
