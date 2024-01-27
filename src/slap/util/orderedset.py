import collections
import functools
import typing as t

T = t.TypeVar("T")
T_OrderedSet = t.TypeVar("T_OrderedSet", bound="OrderedSet")


@functools.total_ordering
class OrderedSet(t.MutableSet[T]):
    def __init__(self, iterable: t.Optional[t.Iterable[T]] = None) -> None:
        self._index_map: t.Dict[T, int] = {}
        self._content: t.Deque[T] = collections.deque()
        if iterable is not None:
            self.update(iterable)

    def __repr__(self) -> str:
        if not self._content:
            return "%s()" % (type(self).__name__,)
        return "%s(%r)" % (type(self).__name__, list(self))

    def __iter__(self) -> t.Iterator[T]:
        return iter(self._content)

    def __reversed__(self) -> "OrderedSet[T]":
        return OrderedSet(reversed(self._content))

    def __eq__(self, other: t.Any) -> bool:
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return False

    def __le__(self, other: t.Any) -> bool:
        return all(e in other for e in self)

    def __len__(self) -> int:
        return len(self._content)

    def __contains__(self, key: t.Any) -> bool:
        return key in self._index_map

    def __getitem__(self, index: int) -> T:
        return self._content[index]

    def add(self, key: T) -> None:
        if key not in self._index_map:
            self._index_map[key] = len(self._content)
            self._content.append(key)

    def copy(self: T_OrderedSet) -> "T_OrderedSet":
        return type(self)(self)

    def discard(self, key: T) -> None:
        if key in self._index_map:
            index = self._index_map.pop(key)
            del self._content[index]

    def pop(self, last: bool = True) -> T:
        if not self._content:
            raise KeyError("set is empty")
        key = self._content.pop() if last else self._content.popleft()
        self._index_map.pop(key)
        return key

    def update(self, iterable: t.Iterable[T]) -> None:
        for x in iterable:
            self.add(x)
