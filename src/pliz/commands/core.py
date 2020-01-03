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

""" Provides base classes for building nested command parsers. """

from nr.collections import OrderedDict
import argparse
import uuid


class Command(object):
  """ Represents a command that can be selected with a specific name. Can be
  put into a #CommandList to allow selecting a command via the command-line.
  """

  name = None
  description = None

  def __init__(self, name=None):
    if name is not None:
      self.name = name

  def update_parser(self, parser):
    pass

  def handle_unknown_args(self, parser, args, argv):
    if argv:
      parser.error('unknown argument {!r}'.format(argv[0]))

  def execute(self, parser, args):
    raise NotImplementedError


class CommandList(object):
  """ Represents a list of commands. """

  def __init__(self, commands=None):
    self.commands = OrderedDict()
    self._uid = str(uuid.uuid4())
    if commands:
      [self.add(x) for x in commands]

  def add(self, command):  # type: (Command)
    if command.name in self.commands:
      raise ValueError('command {!r} already in list'.format(command.name))
    self.commands[command.name] = command

  def update_parser(self, parser):
    subparser = parser.add_subparsers(dest=self._uid)
    for key, command in self.commands.items():
      parser = subparser.add_parser(key, description=command.description)
      command.update_parser(parser)

  def dispatch(self, parser, args, argv):
    name = getattr(args, self._uid)
    if not name:
      parser.print_help()
      return 0
    command = self.commands[name]
    subparser = next(x for x in parser._actions if
        isinstance(x, argparse._SubParsersAction)).choices[name]
    command.handle_unknown_args(parser, args, argv)
    return command.execute(subparser, args)
