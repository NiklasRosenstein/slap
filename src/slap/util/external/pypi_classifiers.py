
import datetime
import logging
import os
import time

import requests

CACHE_FILENAME = os.path.expanduser('~/.local/slap/classifiers-cache.txt')
CACHE_TTL = 60 * 60 * 24 * 7  # 7 days
CLASSIFIERS_URL = 'https://pypi.org/pypi?%3Aaction=list_classifiers'
logger = logging.getLogger(__name__)
_runtime_cache: list[str] | None = None


def get_classifiers(force_refresh: bool = False) -> list[str]:
  """
  Loads the classifiers list from PyPI. Once loaded, the classifiers are cached on disk and
  in memory. The cache on disk is valid for a maxmium of seven days. Specify the *force_refresh*
  argument to ignore any caches.
  """

  global _runtime_cache
  if not force_refresh and _runtime_cache is not None:
    return list(_runtime_cache)

  def _load_cachefile():
    global _runtime_cache
    with open(CACHE_FILENAME) as fp:
      _runtime_cache = [x.rstrip('\n') for x in fp]
    return list(_runtime_cache)

  has_cachefile = not force_refresh and os.path.isfile(CACHE_FILENAME)
  if has_cachefile and (time.time() - os.path.getmtime(CACHE_FILENAME)) < CACHE_TTL:
    return _load_cachefile()
  try:
    classifiers = requests.get(CLASSIFIERS_URL, timeout=1).text.split('\n')
  except requests.exceptions.ReadTimeout as exc:
    if has_cachefile:
      cache_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(CACHE_FILENAME))
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
