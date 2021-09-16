
"""
Strappin' boots and boilin' plates.
"""

import os

import click

from shut.commands import shut, project
from shut.data import load_string
from shut.model.package import PackageModel
from shut.utils.io.virtual import TerminalWriteCallbacks, VirtualFiles


@shut.group('init')
def init(): ...


@init.command('mkdocs')
@click.option('-d', '--dry', is_flag=True)
def _init_mkdocs(dry: bool) -> None:
  model = project.load()
  readme_file = model.get_readme_file() if isinstance(model, PackageModel) else None

  files = VirtualFiles()
  files.add_static('docs/mkdocs.yml', load_string('templates/mkdocs/mkdocs.yml'))
  files.add_static('docs/.gitignore', load_string('templates/mkdocs/.gitignore'))

  if readme_file:
    files.add_symlink('docs/src/index.md', os.path.abspath(readme_file))
  else:
    files.add_static('docs/src/index.md', load_string('templates/mkdocs/src/index.md'))

  callbacks = TerminalWriteCallbacks()
  files.write_all(callbacks=callbacks, dry=dry)
