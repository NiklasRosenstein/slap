from __future__ import annotations

import io
import typing as t

T = t.TypeVar("T")
SubstRange = t.Tuple[int, int, str]


def substitute_ranges(text: str, ranges: t.Iterable[SubstRange], is_sorted: bool = False) -> str:
    """Replaces parts of *text* using the specified *ranges* and returns the new text. Ranges must not overlap.
    *is_sorted* can be set to `True` if the input *ranges* are already sorted from lowest to highest starting index to
    optimize the function.
    """

    if not is_sorted:
        ranges = sorted(ranges, key=lambda x: x[0])

    out = io.StringIO()
    max_end_index = 0
    for index, (istart, iend, subst) in enumerate(ranges):
        if iend < istart:
            raise ValueError(f"invalid range at index {index}: (istart: {istart!r}, iend: {iend!r})")
        if istart < max_end_index:
            raise ValueError(f"invalid range at index {index}: overlap with previous range")

        subst = str(subst)
        out.write(text[max_end_index:istart])
        out.write(subst)
        max_end_index = iend

    out.write(text[max_end_index:])
    return out.getvalue()


def longest_common_substring(
    seq1: t.Sequence[T],
    seq2: t.Sequence[T],
    *args: t.Sequence[T],
    start_only: bool = False,
) -> t.Sequence[T]:
    """Finds the longest common contiguous sequence of elements in *seq1* and *seq2* and returns it."""

    longest: tuple[int, int] = (0, 0)
    for i in (0,) if start_only else range(len(seq1)):
        for j in (0,) if start_only else range(len(seq2)):
            k = 0
            while (i + k < len(seq1) and (j + k) < len(seq2)) and seq1[i + k] == seq2[j + k]:
                k += 1
            if k > longest[1] - longest[0]:
                longest = (i, i + k)

    result = seq1[longest[0] : longest[1]]
    if args:
        result = longest_common_substring(result, *args, start_only=start_only)
    return result
