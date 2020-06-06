# -*- coding: utf8 -*-
# Copyright (c) 2019 Niklas Rosenstein
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

from nr.databind.core import Field, ObjectMapper, Struct
from nr.stream import Stream
from shore.util.version import Version
from termcolor import colored
from typing import Optional, TextIO
import os
import re
import shutil
import textwrap
import yaml


class ChangelogEntry(Struct):
  types = Field([str])
  issues = Field([(str, int)], default=list)
  components = Field([str])
  description = Field(str)


class Changelog:

  RENDERERS = {}

  def __init__(self, filename: str, version: Optional[Version], mapper: ObjectMapper) -> None:
    self.filename = filename
    self.version = version
    self.mapper = mapper
    self.entries = []

  def exists(self) -> bool:
    return os.path.isfile(self.filename)

  def load(self) -> None:
    with open(self.filename) as fp:
      data = yaml.safe_load(fp)
    self.entries = self.mapper.deserialize(data, [ChangelogEntry], filename=self.filename)

  def save(self, create_directory: bool = False) -> None:
    if create_directory:
      os.makedirs(os.path.dirname(self.filename), exist_ok=True)
    data = self.mapper.serialize(self.entries, [ChangelogEntry])
    with open(self.filename, 'w') as fp:
      yaml.safe_dump(data, fp, sort_keys=False)

  def add_entry(self, entry: ChangelogEntry) -> None:
    self.entries.append(entry)

  def render_as(self, fp: TextIO, format: str) -> None:
    self.RENDERERS[format](fp, self)


class ChangelogManager:

  TYPES = frozenset(['fix', 'improvement', 'docs', 'change', 'refactor', 'feature'])

  def __init__(self, directory: str, mapper: ObjectMapper) -> None:
    self.directory = directory
    self.mapper = mapper
    self._cache = {}

  def _get(self, name: str, version: Optional[str]) -> Changelog:
    key = (name, str(version))
    if key in self._cache:
      return self._cache[key]
    changelog = Changelog(os.path.join(self.directory, name), version, self.mapper)
    if os.path.isfile(changelog.filename):
      changelog.load()
    self._cache[key] = changelog
    return changelog

  @property
  def unreleased(self) -> Changelog:
    return self._get('_unreleased.yml', None)

  def version(self, version: Version) -> Changelog:
    return self._get(str(version) + '.yml', version)

  def release(self, version: Version) -> Changelog:
    """
    Renames the unreleased changelog to the file name for the specified *version*.
    """

    unreleased = self.unreleased
    os.rename(unreleased.filename, self.version(version).filename)
    self._cache.clear()
    return self.version(version)


def _group_entries_by_component(entries):
  key = lambda x: x.components[0]
  return list(Stream.sortby(entries, key).groupby(key, collect=list))


def render_changelog_for_terminal(fp: TextIO, changelog: Changelog) -> None:
  """
  Renders a #Changelog for the terminal to *fp*.
  """

  def _md_term_stylize(text: str) -> str:
    def _code(m):
      return colored(m.group(1), 'cyan')
    def _issue_ref(m):
      return colored(m.group(0), 'yellow', attrs=['bold'])
    text = re.sub(r'`([^`]+)`', _code, text)
    text = re.sub(r'#\d+', _issue_ref, text)
    return text

  def _fmt_issue(i):
    if str(i).isdigit():
      return '#' + str(i)
    return i

  def _fmt_issues(entry):
    if not entry.issues:
      return None
    return '(' + ', '.join(colored(_fmt_issue(i), 'yellow', attrs=['underline']) for i in entry.issues) + ')'

  def _fmt_types(entry):
    return ', '.join(colored(f, attrs=['bold']) for f in entry.types)

  def _fmt_components(entry):
    if len(entry.components) <= 1:
      return None
    return '(' + ', '.join(colored(f, 'red', attrs=['bold', 'underline']) for f in entry.components[1:]) + ')'

  if hasattr(shutil, 'get_terminal_size'):
    width = shutil.get_terminal_size((80, 23))[0]
  else:
    width = 80

  # Explode entries by component.
  for component, entries in _group_entries_by_component(changelog.entries):
    maxw = max(len(', '.join(x.types)) for x in entries)
    fp.write(colored(component or 'No Component', 'red', attrs=['bold', 'underline']) + '\n')
    for entry in entries:
      lines = textwrap.wrap(entry.description, width - (maxw + 4))
      suffix_fmt = ' '.join(filter(bool, (_fmt_issues(entry), _fmt_components(entry))))
      lines[-1] += ' ' + suffix_fmt
      delta = maxw - len(', '.join(entry.types))
      fp.write('  {} {}\n'.format(colored((_fmt_types(entry) + ':') + ' ' * delta, attrs=['bold']), _md_term_stylize(lines[0])))
      for line in lines[1:]:
        fp.write('  {}{}\n'.format(' ' * (maxw+2), _md_term_stylize(line)))


def render_changelog_as_markdown(fp: TextIO, changelog: Changelog) -> None:

  def _fmt_issue(i):
    if str(i).isdigit():
      return '#' + str(i)
    return i

  def _fmt_issues(entry):
    if not entry.issues:
      return None
    return '(' + ', '.join(_fmt_issue(i) for i in entry.issues) + ')'

  fp.write('## {}\n\n'.format(changelog.version or 'unreleased'))
  for component, entries in _group_entries_by_component(changelog.entries):
    fp.write('* __{}__\n'.format(component))
    for entry in entries:
      description ='**' + ', '.join(entry.types) + '**: ' + entry.description
      if entry.issues:
        description += ' ' + _fmt_issues(entry)
      lines = textwrap.wrap(description, 80)
      fp.write('  * {}\n'.format(lines[0]))
      for line in lines[1:]:
        fp.write('    {}\n'.format(line))


Changelog.RENDERERS.update({
  'terminal': render_changelog_for_terminal,
  'markdown': render_changelog_as_markdown,
})
