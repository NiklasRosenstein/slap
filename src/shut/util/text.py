
import io
import typing as t

SubstRange = tuple[int, int, str]


def substitute_ranges(text: str, ranges: t.Iterable[SubstRange], is_sorted: bool = False) -> str:
  """ Replaces parts of *text* using the specified *ranges* and returns the new text. Ranges must not overlap.
  *is_sorted* can be set to `True` if the input *ranges* are already sorted from lowest to highest starting index to
  optimize the function.
  """

  if not is_sorted:
    ranges = sorted(ranges, key=lambda x: x[0])

  out = io.StringIO()
  max_end_index = 0
  for index, (istart, iend, subst) in enumerate(ranges):
    if iend < istart:
      raise ValueError(f'invalid range at index {index}: (istart: {istart!r}, iend: {iend!r})')
    if istart < max_end_index:
      raise ValueError(f'invalid range at index {index}: overlap with previous range')

    subst = str(subst)
    out.write(text[max_end_index:istart])
    out.write(subst)
    max_end_index = iend

  out.write(text[max_end_index:])
  return out.getvalue()
