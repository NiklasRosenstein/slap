# -*- coding: utf8 -*-
# Copyright (c) 2019 Niklas Rosenstein
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

""" A tiny client for the DejaCode license library. """

import bs4
import re
import requests
import textwrap

BASE_URL = 'https://enterprise.dejacode.com/licenses/public/{}/'


def _get_table_value_by_key(soup, key):
  regex = re.compile('\s*' + re.escape(key) + '\s*')
  item = soup.find('span', text=regex)
  if item is None:
    raise ValueError('<span/> for {!r} not found'.format(key))
  value = item.parent.findNext('dd').find('pre').text
  if value == '\xa0':
    value = ''
  return value or None


def _get_license_text(soup):
  tab = soup.find(id='tab_license-text')
  if tab is None:
    raise ValueError('#tab_license-text not found')
  pre = soup.find('div', {'class': 'clipboard'}).find('pre')
  return pre.text


def get_license_metadata(license_name):
  """ Retrives the HTML metadata page for the specified license from the
  DejaCode website and extracts information such as the name, category,
  license type, standard notice and license text. """

  url = BASE_URL.format(license_name.replace(' ', '-').lower())
  html = requests.get(url).text
  soup = bs4.BeautifulSoup(html, 'html.parser')

  extract_keys = ['Key', 'Name', 'Short Name', 'Category', 'License type',
    'License profile', 'License style', 'Owner', 'SPDX short identifier',
    'Keywords', 'Standard notice', 'Special obligations', 'Publication year',
    'URN', 'Dataspace', 'Homepage URL', 'Text URLs', 'OSI URL', 'FAQ URL',
    'Guidance URL', 'Other URLs']

  data = {}
  for key in extract_keys:
    data[key.replace(' ', '_').lower()] = _get_table_value_by_key(soup, key)
  data['publication_year'] = int(data['publication_year'])
  if data['standard_notice']:
    data['standard_notice'] = textwrap.dedent(data['standard_notice'])
  data['license_text'] = _get_license_text(soup)

  return data


def wrap_license_text(license_text, width=79):
  lines = []
  for line in license_text.split('\n'):
    line = line.split(' ')
    length = sum(map(len, line)) + len(line) - 1
    if length > width:
      words = []
      length = -1
      for word in line:
        if length + 1 + len(word) >= width:
          lines.append(' '.join(words))
          words = []
          length = -1
        else:
          words.append(word)
          length += len(word) + 1
      if words:
        lines.append(' '.join(words))
    else:
      lines.append(' '.join(line))
  return '\n'.join(lines)
