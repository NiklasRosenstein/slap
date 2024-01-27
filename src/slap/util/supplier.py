from __future__ import annotations

from typing import Callable, TypeVar

T_co = TypeVar("T_co", covariant=True)
T_Supplier = TypeVar("T_Supplier", bound="Supplier")
Supplier = Callable[[], T_co]
