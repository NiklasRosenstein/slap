# -*- coding: utf8 -*-
# Copyright (c) 2021 Niklas Rosenstein
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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Generic, Type, TypeVar

from shut.utils.io.virtual import VirtualFiles
from shut.utils.type_registry import TypeRegistry

if TYPE_CHECKING:
  from shut.model.abstract import AbstractProjectModel

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
T_AbstractProjectModel = TypeVar('T_AbstractProjectModel', bound='AbstractProjectModel')

__all__ = [
  'VersionRef',
  'Renderer',
  'register_renderer',
  'get_files',
  'get_version_refs',
]


@dataclass
class VersionRef:
  filename: str
  start: int
  end: int
  value: str


class Renderer(Generic[T_AbstractProjectModel], metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def get_files(self, files: VirtualFiles, obj: T_AbstractProjectModel) -> None:
    pass

  def get_version_refs(self, obj: T_AbstractProjectModel) -> Iterable[VersionRef]:
    return; yield


registry = TypeRegistry[Renderer[T_AbstractProjectModel]]()


def register_renderer(t: Type[T_AbstractProjectModel], renderer: Type[Renderer[T_AbstractProjectModel]]) -> None:
  """
  Register the *renderer* implementation to run when creating files for *t*.
  """

  registry.put(t, renderer)


def get_files(obj: T_AbstractProjectModel) -> VirtualFiles:
  """
  Gets all the files from the renderers registered to the type of *obj*.
  """

  files = VirtualFiles()
  for renderer in map(lambda r: r(), registry.for_type(type(obj))):
    renderer.get_files(files, obj)
  for renderer in obj.get_auxiliary_renderers():
    renderer.get_files(files, obj)
  return files


def get_version_refs(obj: T_AbstractProjectModel) -> Iterable[VersionRef]:
  """
  Gets all version refs returned by registered for type *T_co*.
  """

  for renderer in registry.for_type(type(obj)):
    yield from renderer().get_version_refs(obj)
