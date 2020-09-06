
import os
from pytest import raises
from shut.model.requirements import Requirement, VendoredRequirement, VersionSelector


def test_parse_requirement():
  assert Requirement.parse('python') == Requirement('python')
  assert Requirement.parse('python') == Requirement('python', VersionSelector.ANY)
  assert Requirement.parse('python 3.4') == Requirement('python', VersionSelector('3.4'))
  assert Requirement.parse('python ^2.7|^3.4') == Requirement('python', VersionSelector('^2.7|^3.4'))

  assert Requirement.parse('mypackage[a,b,c]') == Requirement('mypackage', VersionSelector.ANY, ['a', 'b', 'c'])
  assert Requirement.parse('mypackage[a ,b,c]') == Requirement('mypackage', VersionSelector.ANY, ['a', 'b', 'c'])
  assert Requirement.parse('mypackage[c,a,b]') == Requirement('mypackage', VersionSelector.ANY, ['a', 'b', 'c'])
  assert Requirement.parse('mypackage[c,a,b] ~0.4.2') == Requirement('mypackage', VersionSelector('~0.4.2'), ['a', 'b', 'c'])

  with raises(ValueError):
    Requirement.parse('mypackage[]')
  with raises(ValueError):
    Requirement.parse('mypackage[] ~0.4.2')
  with raises(ValueError):
    Requirement.parse('vendored/liba')


def test_parse_vendored_requirememt():
  assert VendoredRequirement.parse('./vendored/liba') == \
    VendoredRequirement(VendoredRequirement.Type.Path, './vendored/liba')
  assert VendoredRequirement.parse('vendored/liba', fallback_to_path=True) == \
    VendoredRequirement(VendoredRequirement.Type.Path, './vendored/liba')
  assert VendoredRequirement.parse('git+https://github.com/a/b.git') == \
    VendoredRequirement(VendoredRequirement.Type.Git, 'https://github.com/a/b.git')

  with raises(ValueError):
    VendoredRequirement.parse('vendored/liba')
  with raises(ValueError):
    VendoredRequirement.parse('git+without_url')
  with raises(ValueError):
    VendoredRequirement.parse('hg+https://mercurial.org/a/b.hg')

  assert VendoredRequirement(VendoredRequirement.Type.Path, 'vendored/liba').to_pip_args('root', True) == \
    ['-e', os.path.normpath('root/vendored/liba')]
  assert VendoredRequirement(VendoredRequirement.Type.Path, 'vendored/liba').to_pip_args('root', False) == \
    [os.path.normpath('root/vendored/liba')]
  # Ensure that to_pip_args() returns a Path that Pip must recognize as a path as well.
  assert VendoredRequirement(VendoredRequirement.Type.Path, 'liba').to_pip_args('.', False) == \
    [os.path.join('.', 'liba')]
