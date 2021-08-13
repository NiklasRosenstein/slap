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
import enum
import datetime
import hashlib
import json
import os
import shlex
import shutil
import socket
import subprocess as sp
import sys
import textwrap
import traceback
import types
from dataclasses import dataclass, field
from typing import Dict, Optional, List, TYPE_CHECKING

from nr.preconditions import check_not_none
from databind.core import annotations as A
from shut.model.requirements import Requirement

if TYPE_CHECKING:
  from shut.model.package import PackageModel

__all__ = [
  'TestStatus',
  'TestEnvironment',
  'StackTrace',
  'TestCrashReport',
  'TestCase',
  'TestRun',
  'Runtime',
  'Virtualenv',
  'BaseTestDriver',
]


class TestStatus(enum.Enum):
  PASSED = enum.auto()  #: The test passed.
  FAILED = enum.auto()  #: The test failed.
  SKIPPED = enum.auto()  #: The test was skipped.
  ERROR = enum.auto()  #: An error occurred when running the test.


@dataclass
class TestEnvironment:
  python_version: str
  platform: Optional[str]


@dataclass
class StackTrace:
  filename: str
  lineno: int
  message: str

  @classmethod
  def from_traceback(cls, tb: Optional[types.TracebackType]) -> List['StackTrace']:
    result = []
    while tb:
      result.append(cls(filename=tb.tb_frame.f_code.co_filename, lineno=tb.tb_frame.f_lineno, message=''))
      tb = tb.tb_next
    return result


@dataclass
class TestCrashReport:
  filename: str
  lineno: int
  message: str
  traceback: List[StackTrace]
  longrepr: str

  @classmethod
  def current_exception(cls) -> 'TestCrashReport':
    exc = sys.exc_info()
    if exc is None:
      raise RuntimeError('no current exception')
    tb = exc[2]
    assert tb
    return cls(
      filename=tb.tb_frame.f_code.co_filename,
      lineno=tb.tb_frame.f_lineno,
      message=str(exc[1]),
      traceback=StackTrace.from_traceback(tb),
      longrepr='\n'.join(traceback.format_exception(*exc)))


@dataclass
class TestCase:
  name: str
  duration: float
  filename: str
  lineno: int
  status: TestStatus
  crash: Optional[TestCrashReport]
  stdout: str


@dataclass
class TestError:
  filename: Optional[str]
  longrepr: str


@dataclass
class TestRun:
  started: datetime.datetime
  duration: float
  status: TestStatus
  environment: TestEnvironment
  tests: List[TestCase]
  errors: List[TestError] = field(default_factory=list)
  error: Optional[str] = None


@dataclass
class Runtime:
  python: List[str]
  pip: List[str]
  virtualenv: List[str]

  def __post_init__(self) -> None:
    self._env_info: Optional[Dict[str, Optional[str]]] = None

  @classmethod
  def from_env(self) -> 'Runtime':
    python = shlex.split(os.getenv('PYTHON', 'python'))
    pip_var = os.getenv('PIP')
    pip = shlex.split(pip_var) if pip_var else python + ['-m', 'pip']
    venv_var = os.getenv('VIRTUALENV')
    virtualenv = shlex.split(venv_var) if venv_var else python + ['-m', 'venv']
    return Runtime(python, pip, virtualenv)

  @classmethod
  def from_python3(self, python: List[str]) -> 'Runtime':
    pip = python + ['-m', 'pip']
    virtualenv = python + ['-m', 'venv']
    return Runtime(python, pip, virtualenv)

  def is_venv(self) -> bool:
    """
    Returns #True if the #Runtime refers to a local environment (e.g. Virtualenv).

    Todo: Detect Conda environments as local environments?
    """

    # See https://stackoverflow.com/a/42580137/791713
    info = self._get_environment_info()
    return bool(info['real_prefix'] or (info['base_prefix'] and info['prefix'] != info['base_prefix']))

  def get_executable_path(self) -> str:
    return check_not_none(self._get_environment_info()['executable'])

  def get_hash_code(self) -> str:
    """
    Returns a has that identifies the runtime. This is a combination of the environment info
    and the creation timestamp of the Python executable (which we expect to only be changed if
    a virtualenv is re-created).
    """

    path = self.get_executable_path()
    ctime = os.path.getctime(path)
    return hashlib.md5(f'{socket.gethostname()}-{path}-{ctime}'.encode()).hexdigest()

  def _get_environment_info(self) -> Dict[str, Optional[str]]:
    if self._env_info is None:
      code = textwrap.dedent('''
        import sys, platform, json
        print(json.dumps({
          "executable": sys.executable,
          "version": sys.version,
          "platform": platform.platform(),
          "prefix": sys.prefix,
          "base_prefix": getattr(sys, 'base_prefix', None),
          "real_prefix": getattr(sys, 'real_prefix', None),
        }))
      ''')
      self._env_info = json.loads(sp.check_output(self.python + ['-c', code]).decode())
    return self._env_info

  def get_environment(self) -> TestEnvironment:
    raw = self._get_environment_info()
    version, platform = raw['version'], raw['platform']
    assert version and platform
    return TestEnvironment(version, platform)


@dataclass
class Virtualenv:
  path: str

  def exists(self) -> bool:
    return os.path.isdir(self.path)

  def create(self, runtime: Runtime) -> None:
    """
    Create the virtual environment.
    """

    sp.check_call(runtime.virtualenv + [self.path])

  def rm(self):
    if os.path.isdir(self.path):
      shutil.rmtree(self.path)

  def bin(self, name):
    if os.name == 'nt':
      name += '.exe'
    return os.path.join(self.path, 'Scripts' if os.name == 'nt' else 'bin', name)

  def get_runtime(self) -> Runtime:
    return Runtime.from_python3([self.bin('python')])


@A.union(style=A.union.Style.flat)
class BaseTestDriver(abc.ABC):
  """
  Base class for drivers that can run unit tests for a package.
  """

  @abc.abstractmethod
  def test_package(self, package: 'PackageModel', runtime: Runtime, capture: bool) -> TestRun:
    pass

  @abc.abstractmethod
  def get_test_requirements(self) -> List[Requirement]:
    pass
