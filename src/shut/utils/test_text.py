
from pytest import raises

from .text import substitute_ranges


def test_substitute_ranges():
  text = 'abcdefghijklmnopqrstuvwxyz'
  assert substitute_ranges(text, [
    (1, 4, 'SPAM'),
    (10, 11, 'EGGS'),
  ]) == 'aSPAMefghijEGGSlmnopqrstuvwxyz'

  assert substitute_ranges(text, [
    (10, 11, 'EGGS'),
    (1, 4, 'SPAM'),
  ]) == 'aSPAMefghijEGGSlmnopqrstuvwxyz'

  with raises(ValueError) as excinfo:
    substitute_ranges(text, [
      (10, 11, 'EGGS'),
      (1, 4, 'SPAM'),
    ], is_sorted=True)
  assert str(excinfo.value) == 'invalid range at index 1: overlap with previous range'

  with raises(ValueError) as excinfo:
    substitute_ranges(text, [
      (1, 4, 'SPAM'),
      (3, 5, 'EGGS'),
    ])
  assert str(excinfo.value) == 'invalid range at index 1: overlap with previous range'
