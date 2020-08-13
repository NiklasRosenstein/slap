# -*- coding: utf8 -*-
# Copyright (c) 2020 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import abc
from typing import Generic, Iterable, List, T, Type

from shut.model import AbstractProjectModel
from shut.model.target import Target, TargetId
from shut.utils.type_registry import TypeRegistry

__all__ = [
  'Publisher',
  'PublisherProvider',
  'register_publisher_provider',
  'get_publishers',
]


class Publisher(Target, metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def publish(self, verbose: bool) -> bool:
    pass


class PublisherProvider(Generic[T], metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def get_publishers(self) -> List[Publisher]:
    pass


registry = TypeRegistry[PublisherProvider[AbstractProjectModel]]()


def register_publisher_provider(type_: Type[T], provider_class: Type[PublisherProvider[T]]) -> None:
  registry.put(type_, provider_class)


def get_publishers(obj: T) -> Iterable[Publisher]:
  return concat(provider().get_publishers(obj) for provider in registry.for_type(type(obj)))
