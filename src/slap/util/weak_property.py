from __future__ import annotations

import weakref
from typing import Any, Generic, Literal, Optional, TypeVar, overload

T = TypeVar("T")


class WeakProperty(Generic[T]):
    def __init__(self, attr_name: str, once: bool = False) -> None:
        self._name = attr_name
        self._once = once
        self._value: Optional[weakref.ReferenceType[T]] = None

    def __set__(self, instance: Any, value: T) -> None:
        has_value: Optional[weakref.ReferenceType[T]] = getattr(instance, self._name, None)
        if self._once and has_value is not None:
            raise RuntimeError("property can not be set more than once")
        setattr(instance, self._name, weakref.ref(value))

    def __get__(self, instance: Any, owner: Any) -> T:
        if instance is None:
            raise AttributeError()
        has_value: Optional[weakref.ReferenceType[T]] = getattr(instance, self._name, None)
        if has_value is None:
            raise AttributeError("property value is not set")
        value = has_value()
        if value is None:
            raise RuntimeError("lost weak reference")
        return value


class OptionalWeakProperty(WeakProperty[Optional[T]]):
    def __set__(self, instance: Any, value: Optional[T]) -> None:
        has_value: Optional[weakref.ReferenceType[T]] = getattr(instance, self._name, None)
        if self._once and has_value is not None:
            raise RuntimeError("property can not be set more than once")
        setattr(instance, self._name, weakref.ref(value) if value is not None else None)

    def __get__(self, instance: Any, owner: Any) -> Optional[T]:
        if instance is None:
            raise AttributeError()
        try:
            return super().__get__(instance, owner)
        except AttributeError:
            return None


@overload
def weak_property(attr_name: str, once: bool = False, optional: Literal[False] = False) -> Any: ...


@overload
def weak_property(attr_name: str, once: bool = False, optional: Literal[True] = True) -> Any | None: ...


def weak_property(attr_name: str, once: bool = False, optional: bool = False) -> Any | None:
    return WeakProperty(attr_name, once) if optional else OptionalWeakProperty(attr_name, once)
