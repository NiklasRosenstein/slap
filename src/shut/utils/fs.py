
import os
import typing as t


def get_file_in_directory(directory: str, prefix: str, preferred: t.List[str]) -> t.Optional[str]:
  """
  Returns a file in *directory* that is either in the *preferred* list or starts with
  specified *prefix*.
  """

  choices = []
  for name in sorted(os.listdir(directory)):
    if name in preferred:
      break
    if name.startswith(prefix):
      choices.append(name)
  else:
    if choices:
      return choices[0]
    return None

  return os.path.join(directory, name)
