
import re
import os
import subprocess as sp
from pathlib import Path

from slap import __version__
from slap.plugins import ChangelogUpdateAutomationPlugin


class GithubActionsChangelogUpdateAutomationPlugin(ChangelogUpdateAutomationPlugin):
  """ A plugin for use in GitHub Actions via `slap changelog update-pr --use github-actions` which will do all steps
  to push the updated changelogs back to a pull request branch. It should be used only in an action that is run as
  part of a GitHub pull request.

  The GitHub Action should be configured like this:

  ```yaml
  update-changelogs:
    if: github.event_name == 'pull_request'
    permissions:
      contents: write
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python 3.10
      uses: actions/setup-python@v2
      with: {{ python-version: '3.10' }}
    - name: Install Slap
      run: pip install slap-cli==1.0.2
    - name: Update PR references in changelogs
      run: slap changelog update-pr --use github-actions
  ```

  GitHub environment variables used:

  * `GITHUB_HEAD_REF`
  * `GITHUB_BASE_REF`
  * `GITHUB_REF` (the github PR number formatted as `refs/pull/{id}`)

  Additional environment variables to control the plugin:

  * `GIT_USER_NAME` (defaults to `GitHub Action`)
  * `GIT_USER_EMAIL` (defaults to `github-action@users.noreply.github.com`)
  * `GIT_COMMIT_MESSAGE` (defaults to `Update changelog PR references`)
  * `GIT_SHOW_DIFF` (if set, runs "git diff" before publishing changes)
  """

  def initialize(self) -> None:
    sp.check_output(['git', 'fetch'], stderr=sp.PIPE)
    sp.check_output(['git', 'checkout', 'origin/' + os.environ['GITHUB_HEAD_REF']], stderr=sp.PIPE)
    sp.check_output(['git', 'checkout', '-b', os.environ['GITHUB_HEAD_REF']], stderr=sp.PIPE)

  def get_base_ref(self) -> str:
    return 'origin/' + os.environ['GITHUB_BASE_REF']

  def get_pr(self) -> str:
    ref = os.environ['GITHUB_REF']
    match = re.match(r'refs/pull/(\d+)', ref)
    if not match:
      raise EnvironmentError(f'could not determine Pull Request ID from GITHUB_REF="{ref}"')
    return match.group(1)

  def publish_changes(self, changed_files: list[Path]) -> None:
    user_name = os.environ.get('GIT_USER_NAME', 'GitHub Action')
    user_email = os.environ.get('GIT_USER_EMAIL', 'github-action@users.noreply.github.com')
    commit_message = os.environ.get('GIT_COMMIT_MESSAGE', 'Update changelog PR references')
    if os.getenv('GIT_SHOW_DIFF'):
      sp.check_output(['git', 'diff'], stderr=sp.PIPE)
    sp.check_output(['git', 'add'] + [str(f) for f in changed_files], stderr=sp.PIPE)
    sp.check_output(['git', '-c', 'user.name=' + user_name, '-c', 'user.email=' + user_email, 'commit', '-m', commit_message], stderr=sp.PIPE)
    sp.check_output(['git', 'push', 'origin', os.environ['GITHUB_HEAD_REF']], stderr=sp.PIPE)
