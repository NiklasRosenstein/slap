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

from typing import Iterable, List, Optional
import collections
import subprocess

Branch = collections.namedtuple('Branch', 'name,current')
FileStatus = collections.namedtuple('FileStatus', 'mode,filename')


def add(files: List[str], path: str = None):
  command = ['git', 'add', '--'] + files
  subprocess.check_call(command, cwd=path)


def branches(path: str = None) -> List[Branch]:
  command = ['git', 'branch']
  results = []
  for line in subprocess.check_output(command, cwd=path).decode().splitlines():
    current = False
    if line.startswith('*'):
      line = line[1:]
      current = True
    results.append(Branch(line.strip(), current))
  return results


def current_branch(path: str = None) -> str:
  for branch in branches(path):
    if branch.current:
      return branch.name
  raise RuntimeError('no curent branch ?')


def push(*refs, remote='origin', path: str = None):
  command = ['git', 'push', remote] + list(refs)
  subprocess.check_call(command, cwd=path)


def porcelain() -> Iterable[FileStatus]:
  for line in subprocess.getoutput('git status --porcelain').split('\n'):
    mode, filename = line.strip().partition(' ')[::2]
    yield FileStatus(mode, filename)


def add(filenames: List[str]):
  subprocess.check_call(['git', 'add'] + filenames)


def commit(message, allow_empty: bool=False):
  command = ['git', 'commit', '-m', message]
  if allow_empty:
    command.append('--allow-empty')
  subprocess.check_call(command)


def tag(tag_name: str, force: bool=False):
  command = ['git', 'tag', tag_name] + (['-f'] if force else [])
  subprocess.check_call(command)


def rev_parse(rev: str, path: str = None) -> Optional[str]:
  command = ['git', 'rev-parse', rev]
  try:
    return subprocess.check_output(command, stderr=subprocess.STDOUT, cwd=path).decode().strip()
  except subprocess.CalledProcessError:
    return None


def rev_list(rev: str, path: str = None) -> List[str]:
  command = ['git', 'rev-list', rev]
  if path:
    command += ['--', path]
  revlist = subprocess.check_output(command, stderr=subprocess.STDOUT).decode().strip().split('\n')
  if revlist == ['']:
    revlist = []
  return revlist


def has_diff(path: str = None) -> bool:
  try:
    subprocess.check_call(['git', 'diff', '--exit-code'], stdout=subprocess.PIPE)
    return False
  except subprocess.CalledProcessError as exc:
    if exc.returncode == 1:
      return True
    raise
