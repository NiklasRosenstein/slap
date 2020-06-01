
from shore.model import Package, VersionSelector


def test_package_is_universal():
  package = Package(name='test', description='')

  assert not package.requirements.python
  assert package.is_universal()

  package.requirements.python = VersionSelector('2.7')
  assert not package.is_universal()

  package.requirements.python = VersionSelector('3.4')
  assert not package.is_universal()

  package.requirements.python = VersionSelector('>= 3.4')
  assert not package.is_universal()

  package.requirements.python = VersionSelector('^2.7 | ^3.3')
  assert package.is_universal()

  package.requirements.python = VersionSelector('>= 2.7 | >= 3.3')
  assert package.is_universal()

  package.requirements.python = VersionSelector('~2.7 | ~2.10')
  assert not package.is_universal()

  package.requirements.python = VersionSelector('2|3')
  assert package.is_universal()
