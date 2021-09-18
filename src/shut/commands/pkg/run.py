
import os
import shlex
import sys
import typing as t

import click

from shut.commands import project
from shut.commands.pkg import pkg
from shut.model.package import PackageModel


@pkg.command('run')
@click.argument('script')
@click.argument('args', nargs=-1)
def init(script: str, args: t.List[str]):
  package: PackageModel = project.load_or_exit(expect=PackageModel)
  if script not in package.scripts:
    raise ValueError(f'script {script!r} is not defined on {package.name!r}')
  command = package.scripts[script] + ' ' + ' '.join(map(shlex.quote, args))
  sys.exit(os.system(command))
