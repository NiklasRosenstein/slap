
from shut.model.version import Version
from shut.model.requirements import VersionSelector
import pytest


def test_parsing():
  v = Version('1.0.0')
  assert v.base_version == '1.0.0'
  assert v.commit_distance is None
  assert v.sha is None

  v = Version('1.0.0-4-g532aef1')
  assert v.base_version == '1.0.0'
  assert v.commit_distance == 4
  assert v.sha == '532aef1'

  with pytest.raises(ValueError):
    Version('1.0.0-4-g532aes1')


def test_comparison():
  pairs = [
    ('1.0.0', '1.0.1'),
    ('1.0.0', '1.0.0-7-g324aef2'),
    ('1.0.0-7-g324eaf2', '1.0.0-8-g123abcd'),
    ('1.0.0-7-g123abcd', '1.0.1'),
    ('0.0.2.post1', '0.0.2.post1-7-gb5b3fda'),
  ]

  for a, b in pairs:
    assert Version(a) < Version(b)
    assert not (Version(b) < Version(a))
    assert Version(b) > Version(a)
    assert not (Version(a) > Version(b))


def test_version_selector():
  assert VersionSelector('1.0.0').to_setuptools() == '==1.0.0'
  assert VersionSelector('~1.0.0').to_setuptools() == '>=1.0.0,<1.1.0'
  assert VersionSelector('^1.0.0').to_setuptools() == '>=1.0.0,<2.0.0'
  assert VersionSelector('<=1.0.0,>0.5.0').to_setuptools() == '<=1.0.0,>0.5.0'
