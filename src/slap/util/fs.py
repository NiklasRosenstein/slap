from __future__ import annotations

import contextlib
import os
import tempfile
import typing as t
from pathlib import Path

import typing_extensions as te

StrPath: te.TypeAlias = "str | Path"


@t.overload
def atomic_write(
    path: StrPath,
    mode: te.Literal["w"],
    rename_mode: te.Literal["posix", "windows"] | None,
) -> t.ContextManager[t.TextIO]: ...


@t.overload
def atomic_write(
    path: StrPath,
    mode: te.Literal["wb"],
    rename_mode: te.Literal["posix", "windows"] | None,
) -> t.ContextManager[t.BinaryIO]: ...


@contextlib.contextmanager  # type: ignore
def atomic_write(
    path: StrPath,
    mode: te.Literal["w", "wb"],
    rename_mode: te.Literal["posix", "windows"] | None = None,
) -> t.Iterator[t.IO]:
    """Write to a temporarily file, then rename on file closure. If an error occurs while the context manager is active,
    the temporary file will be deleted instead and if an original file existed before it will not be modified. On
    Windows systems, the file cannot be replaced in an atomic operation, so it will need to be deleted first."""

    if rename_mode is None:
        if os.name == "nt":
            rename_mode = "windows"
        else:
            rename_mode = "posix"

    with tempfile.NamedTemporaryFile(mode, delete=False) as fp:
        try:
            yield fp
        except:  # noqa: E722
            os.remove(fp.name)
            raise
        else:
            fp.flush()
            os.fsync(fp.fileno())
            if rename_mode == "windows" and os.path.isfile(path):
                os.remove(path)
            os.rename(fp.name, path)


@t.overload
def atomic_swap(
    path: StrPath,
    mode: te.Literal["w"],
    always_revert: bool,
) -> t.ContextManager[t.TextIO]: ...


@t.overload
def atomic_swap(
    path: StrPath,
    mode: te.Literal["wb"],
    always_revert: bool,
) -> t.ContextManager[t.BinaryIO]: ...


@contextlib.contextmanager  # type: ignore
def atomic_swap(
    path: StrPath,
    mode: te.Literal["w", "wb"],
    always_revert: bool = False,
) -> t.Iterator[t.IO]:
    """Similar to #atomic_write(), only that this function writes to the *path* directlty instead of a temporary file,
    and save the original version of the file next to it in the same directory by temporarily renaming it. If the
    context exits without error, the old file will be removed. Otherwise, the new file will be deleted and the old file
    will be renamed back to *path*. If *always_revert* is enabled, the original file will be restored even if the
    context exits without errors."""

    path = Path(path)

    with tempfile.NamedTemporaryFile(mode, prefix=path.stem + "~", suffix="~" + path.suffix, dir=path.parent) as old:
        old.close()
        os.rename(path, old.name)

        def _revert():
            if path.is_file():
                path.unlink()
            os.rename(old.name, path)

        try:
            with path.open(mode) as new:
                yield new
        except:  # noqa: E722
            _revert()
            raise
        else:
            if always_revert:
                _revert()
            else:
                os.remove(old.name)


def get_file_in_directory(
    directory: Path,
    prefix: str,
    preferred: list[str],
    case_sensitive: bool = True,
) -> Path | None:
    """Returns a file in *directory* that is either in the *preferred* list or starts with specified *prefix*."""

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
