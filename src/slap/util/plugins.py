""" Helpers to implement a plugin infrastructure in Python. """

from __future__ import annotations

import logging
import typing as t

import importlib_metadata
import typing_extensions as te

T = t.TypeVar("T")

logger = logging.getLogger(__name__)

# NOTE (@NiklasRosenstein): I wished we could use a TypeVar bound to a protocol instead of T, but mypy does
#   not seem to like it.


class NoSuchEntrypointError(RuntimeError):
    pass


@t.overload
def load_entrypoint(group: str, name: str) -> t.Any: ...


@t.overload
def load_entrypoint(group: type[T], name: str) -> type[T]: ...


def load_entrypoint(group: str | type[T], name: str) -> t.Any | type[T]:
    """Load a single entrypoint value. Raises a #RuntimeError if no such entrypoint exists."""

    if isinstance(group, type):
        group_name = group.ENTRYPOINT  # type: ignore
    else:
        group_name = group

    for ep in importlib_metadata.entry_points(group=group_name, name=name):
        value = ep.load()
        break
    else:
        raise NoSuchEntrypointError(f'no entrypoint "{name}" in group "{group}"')

    if isinstance(group, type):
        if not isinstance(value, type):
            raise TypeError(f'entrypoint "{name}" in group "{group}" is not a type (found "{type(value).__name__}")')
        if not issubclass(value, group):  # type: ignore
            raise TypeError(f'entrypoint "{name}" in group "{group}" is not a subclass of {group.__name__}')

    return value


_Iter_Entrypoints_1: te.TypeAlias = "t.Iterator[importlib_metadata.EntryPoint]"
_Iter_Entrypoints_2: te.TypeAlias = "t.Iterator[tuple[str, t.Callable[[], type[T]]]]"


@t.overload
def iter_entrypoints(group: str) -> _Iter_Entrypoints_1: ...


@t.overload
def iter_entrypoints(group: type[T]) -> _Iter_Entrypoints_2: ...


def iter_entrypoints(group: str | type[T]) -> _Iter_Entrypoints_1 | _Iter_Entrypoints_2:
    """Loads all entrypoints from the given group."""

    if isinstance(group, type):
        group_name = group.ENTRYPOINT  # type: ignore
    else:
        group_name = group

    def _make_loader(ep: importlib_metadata.EntryPoint) -> t.Callable[[], type[T]]:
        def loader():
            assert isinstance(group, type)
            value = ep.load()
            if not isinstance(value, type):
                raise TypeError(
                    f'entrypoint "{ep.name}" in group "{group}" is not a type (found "{type(value).__name__}")'
                )
            if not issubclass(value, group):  # type: ignore
                raise TypeError(f'entrypoint "{ep.name}" in group "{group}" is not a subclass of {group.__name__}')
            return value

        return loader

    for ep in importlib_metadata.entry_points(group=group_name):
        if isinstance(group, type):
            yield ep.name, _make_loader(ep)
        else:
            yield ep
