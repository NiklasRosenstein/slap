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

FileStatus = collections.namedtuple('FileStatus', 'mode,filename')


def porcelain() -> Iterable[FileStatus]:
  for line in subprocess.getoutput('git status --porcelain').split('\n'):
    mode, filename = line.strip().partition(' ')[::2]
    yield FileStatus(mode, filename)


def add(filenames: List[str]):
  subprocess.check_call(['git', 'add'] + filenames)


def commit(message):
  subprocess.check_call(['git', 'commit', '-m', message])


def tag(tag_name: str, force: bool=False):
  command = ['git', 'tag', tag_name] + (['-f'] if force else [])
  subprocess.check_call(command)


def rev_parse(rev: str) -> Optional[str]:
  command = ['git', 'rev-parse', rev]
  try:
    return subprocess.check_output(command, stderr=subprocess.STDOUT).decode().strip()
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
