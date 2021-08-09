
"""
This module uses some pytest features that should all work when using the pytest driver with `shut pkg test`.
"""

import pytest


@pytest.mark.xfail
def test_xfail():
  pass
