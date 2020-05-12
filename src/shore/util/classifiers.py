# -*- coding: utf8 -*-
# Copyright (c) 2020 Niklas Rosenstein
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

from datetime import datetime
from typing import List
import logging
import os
import requests
import time

CACHE_FILENAME = os.path.expanduser('~/.local/shore/classifiers-cache.txt')
CACHE_TTL = 60 * 60 * 24 * 7  # 7 days
CLASSIFIERS_URL = 'https://pypi.org/pypi?%3Aaction=list_classifiers'
logger = logging.getLogger(__name__)
_runtime_cache = None


def get_classifiers() -> List[str]:
  global _runtime_cache
  if _runtime_cache is not None:
    return list(_runtime_cache)

  def _load_cachefile():
    global _runtime_cache
    with open(CACHE_FILENAME) as fp:
      _runtime_cache = [x.rstrip('\n') for x in fp]
    return list(_runtime_cache)

  has_cachefile = os.path.isfile(CACHE_FILENAME)
  if has_cachefile and (time.time() - os.path.getmtime(CACHE_FILENAME)) < CACHE_TTL:
    return _load_cachefile()
  try:
    classifiers = requests.get(CLASSIFIERS_URL, timeout=1).text.split('\n')
  except requests.exceptions.ReadTimeout as exc:
    if has_cachefile:
      cache_timestamp = datetime.fromtimestamp(os.path.getmtime(CACHE_FILENAME))
      message = ' Falling back to cached classifiers (timestamp: {})'.format(cache_timestamp)
    else:
      message = ' Returning no classifiers. Subsequent classifier validation might raise.'
    logger.warning('Error retrieving classifiers from "%s" (%s).%s', CLASSIFIERS_URL, exc, message)
    if has_cachefile:
      return _load_cachefile()
    _runtime_cache = []
    return []
  try:
    os.makedirs(os.path.dirname(CACHE_FILENAME), exist_ok=True)
    with open(CACHE_FILENAME, 'w') as fp:
      fp.writelines((x + '\n' for x in classifiers))
  except:
    logger.exception('Unable to write classifiers cache file.')

  _runtime_cache = classifiers
  return list(classifiers)
