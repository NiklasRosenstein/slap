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

"""
Updates a conda-forge feedstock repository by cloning it, updating the version
details with data from PyPI and pushing it back to the feedstock. The GitHub PR
must still be created manually after this.

Todo:

\b
* Update run requirements and test imports
"""

from nr.interface import override, implements
from shore.__main__ import _load_subject
from termcolor import colored
from typing import List

import click
import logging
import nr.fs
import re
import requests
import subprocess
import sys

logger = logging.getLogger(__name__)


def _call(*args, **kwargs):
  proc = subprocess.Popen(*args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
  stdout, _ = proc.communicate()
  if proc.returncode != 0:
    print(colored(stdout.decode(), 'red'))
    sys.exit(proc.returncode)


@click.command(help=__doc__)
@click.option('--update-feedstock', is_flag=True, help='Update the conda-forge feedstock for the current version.')
def main(update_feedstock):

  if not update_feedstock:
    logger.error('no operation specified')
    sys.exit(1)

  subject = _load_subject()

  repo_name = 'conda-forge/{}-feedstock'.format(subject.name)
  pypi_package_name = subject.name
  version = str(subject.version)
  clone_url = 'git@github.com:' + repo_name
  branch_name = 'v' + version

  s_repo_name = colored(repo_name, 'blue')
  s_pypi_package_name = colored(pypi_package_name, 'yellow')
  s_clone_url = colored(clone_url, 'blue')
  s_branch_name = colored(branch_name, 'yellow')

  print('Fetching PyPI record for', s_pypi_package_name, '...')
  url = 'https://pypi.org/pypi/{}/json'.format(pypi_package_name)
  pypi_data = requests.get(url).json()
  if version not in pypi_data['releases']:
    logger.error('No release on PyPI for %s v%s.', s_pypi_package_name, version)
    sys.exit(1)

  sdist = next((x for x in pypi_data['releases'][version] if x['packagetype'] == 'sdist'), None)
  if not sdist:
    logger.error('No sdist on PyPI for %s v%s.', s_pypi_package_name, version)
    sys.exit(1)
  sha256 = sdist['digests']['sha256']

  print('Updating', s_repo_name, 'from PyPI package', s_pypi_package_name + ' v' + version + '.')

  with nr.fs.tempdir() as tmpdir:

    print('Cloning', s_clone_url, '...')
    _call(['git', 'clone', clone_url, tmpdir.name])
    _call(['git', 'checkout', '-b', branch_name], cwd=tmpdir.name)

    recipe_path = nr.fs.join(tmpdir.name, 'recipe', 'meta.yaml')
    with open(recipe_path) as fp:
      recipe = fp.read()

    recipe = re.sub(r'(version = ")([^"]+)"', r'\g<1>' + version + '"', recipe)
    recipe = re.sub(r'(sha256:\s*")([^"]+)"', r'\g<1>' + sha256 + '"', recipe)

    with open(recipe_path, 'w') as fp:
      fp.write(recipe)

    print()
    subprocess.check_call(['git', '--no-pager', 'diff'], cwd=tmpdir.name)
    print()

    _call(['git', 'add', '.'], cwd=tmpdir.name)
    _call(['git', 'commit', '-m', 'Updating recipe for {} v{}.'.format(
      pypi_package_name, version)], cwd=tmpdir.name)

    print('Pushing branch', s_branch_name, 'to', s_clone_url, '...')
    _call(['git', 'push', 'origin', branch_name, '--set-upstream'], cwd=tmpdir.name)


if __name__ == '__main__':
  main()
