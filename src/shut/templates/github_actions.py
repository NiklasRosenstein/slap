
import dataclasses
import re
import os
import subprocess as sp
import typing as t
from pathlib import Path

import yaml
from databind.core.annotations import alias, fieldinfo
from typing_extensions import Annotated

from shut import __version__
from shut.data import load_string,render_mako_template
from shut.model import T_AbstractProjectModel
from shut.model.package import PackageModel
from shut.model.requirements import Requirement
from shut.renderers import Renderer
from shut.utils.io.virtual import VirtualFiles

# Let's be honest, you should not use anything older than this... Even 3.4 may be a stretch.
PYTHON_VERSIONS = ['3.4', '3.5', '3.6', '3.7', '3.8', '3.9']
PYTHON_NIGHTLY = '3.x'


def identify_main_branch(directory: str) -> str:
  """
  Tries to identify the main branch of a repository by checking which branch the remote HEAD is pointing to.
  Returns the branch name without the remote (i.e. `develop` if Git returns `origin/develop`).
  """

  command = ['git', 'branch', '-r', '--points-at', 'refs/remotes/origin/HEAD']
  output = sp.check_output(command, cwd=directory).decode()
  line = next((l for l in output.splitlines() if '->' in l), None)
  if not line:
    raise RuntimeError(f'could not determine main branch of {directory!r}: {output!r}')
  remote_branch = line.split('->')[-1]
  return remote_branch.split('/')[-1].strip()


def select_python_versions(req: Requirement) -> t.List[str]:
  if not req.version.is_semver_selector():
    raise RuntimeError(f'matching non-semver selectors (ie. setuptools style) is not currently supported, please '
      'explicitly specify the python-versions to use in the GitHub Actions template.')
  return [v for v in PYTHON_VERSIONS if req.version.matches(v)] + [PYTHON_NIGHTLY]


def detect_branch_in_action_config(filename: Path) -> str:
  """
  Looks up the branch in the GitHub Action under *filename*. This is used instead of #identify_main_branch()
  when the action already exists to work around https://github.com/NiklasRosenstein/shut/issues/40/.
  """

  with open(filename, encoding='utf8') as fp:
    config = yaml.safe_load(fp)

  # True because "on" is interpreted as a boolean in YAML, even if it's a key..?
  branches = (config.get('on') or config.get(True) or {}).get('push', {}).get('branches', [])
  if not branches:
    raise RuntimeError(f'could not detect branch in GitHub Action {filename!r}')

  return branches[0]


@dataclasses.dataclass
class GithubActionsTemplate(Renderer):
  """
  Renders a GitHub action for Shut.
  """

  #: The name of the GitHub Actions workflow.
  workflow_name: Annotated[str, alias('workflow-name')] = 'Python Package'

  #: The filename of the workflow. Defaults to a name generated from #workflow_name.
  workflow_filename: Annotated[t.Optional[str], alias('workflow-filename')] = None

  #: The branch to run on. If this is not specified, Shut will try to determine the default
  #: branch name by asking which remote branch `refs/remotes/origin/HEAD` points to.
  branch: t.Optional[str] = None

  #: Whether to run on pull requests. Default is #True.
  pull_requests: Annotated[bool, alias('pull-requests')] = True

  #: Whether to generate a step to publish to PyPI.
  pypi_publish: Annotated[bool, alias('pypi-publish')] = False

  #: Whether to do a test publish to https://test.pypi.org before publishing to https://pypi.org.
  #: Only used when #pypi_publish is enabled. Defaults to #True.
  test_publish: Annotated[bool, alias('test-publish')] = True

  #: The python versions to run with. Note that Shut requires at least Python 3.7. If no
  #: Python version is selected, all Python versions from #PYTHON_VERSIONS matching the
  #: the `python` requirement in the package configuration are used, plus #PYTHON_NIGHTLY.
  #
  #: TODO (@NiklasRosenstein): If a Python version below 3.7 is picked, we can set up Conda
  #: instead and install Shut into a Python >=3.7 environment while testing the package
  #: with the requested Python version.
  python_versions: Annotated[t.Optional[t.List[str]], alias('python-versions'), fieldinfo(strict=False)] = None

  # Whether to do isolated unit tests. Defaults to #True.
  isolated_unit_testing: Annotated[bool, alias('isolated-unit-testing')] = True

  #: Generate a job to generate documentation with MkDocs and publish it to gh-pages.
  #: If not specified, will check if there's a `docs` folder in the project.
  #:
  #: TODO (@NiklasRosenstein): The template is currently a but too opinionated about using
  #:  mkdocs and where and how to generate the `changelog.md`.
  docs: t.Optional[bool] = False

  def get_files(self, files: VirtualFiles, obj: T_AbstractProjectModel) -> None:
    # TODO (@NiklasRosenstein): Supporting a mono repo shouldn't be a lot more effort.
    if not isinstance(obj, PackageModel):
      raise RuntimeError(f'github-template can only be used in package.yml')

    if os.getenv('IGNORE_GITHUB_ACTIONS_TEMPLATE') == 'true':
      return

    workflow_filename = self.workflow_filename or (
      re.sub(r'[^\d\w]+', '-', self.workflow_name).strip('-').lower() + '.yml')
    relative_path = f'.github/workflows/{workflow_filename}'
    full_path = Path(obj.get_directory()) / relative_path

    branch = self.branch or (detect_branch_in_action_config(full_path) if
      full_path.exists() else identify_main_branch(obj.get_directory()))

    python_req = obj.get_python_requirement()
    if self.python_versions is None and python_req:
      python_versions = select_python_versions(python_req)
    elif self.python_versions is None:
      python_versions = PYTHON_VERSIONS + [PYTHON_NIGHTLY]
    else:
      if not self.python_versions:
        raise RuntimeError(f'no python_versions specified')
      python_versions = self.python_versions

    docs = True if self.docs else (Path(obj.get_directory()) / 'docs').exists()

    template_string = load_string('templates/github-action.yml')
    context_vars: t.Dict[str, t.Union[bool, str, t.List[str]]] = {
      'workflow_name': self.workflow_name,
      'branch': branch,
      'pypi_publish': self.pypi_publish,
      'pull_requests': self.pull_requests,
      'test_publish': self.test_publish,
      'python_versions': python_versions,
      'isolated_unit_testing': self.isolated_unit_testing,
      'shut_req': '.' if obj.name == 'shut' else f'shut=={__version__}',
      'docs': docs,
    }

    files.add_dynamic(
      relative_path,
      lambda fp: render_mako_template(fp, template_string, context_vars))
