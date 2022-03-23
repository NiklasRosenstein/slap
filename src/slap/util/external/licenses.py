
"""
Scraper for [DejaCode][1] and [SPDX][2].

  [1]: https://enterprise.dejacode.com/licenses/
  [2]: https://spdx.org/licenses/
"""

import dataclasses
import bs4
import re
import requests
import textwrap
import typing as t

from databind.core.settings import Alias

BASE_URL = 'https://enterprise.dejacode.com/licenses/public/{}/'


@dataclasses.dataclass
class SpdxLicense:
  reference: str
  is_deprecated_license_id: t.Annotated[bool, Alias('isDeprecatedLicenseId')]
  details_url: t.Annotated[str, Alias('detailsUrl')]
  reference_number: t.Annotated[int, Alias('referenceNumber')]
  name: str
  license_id: t.Annotated[str, Alias('licenseId')]
  see_also: t.Annotated[list[str], Alias('seeAlso')]
  is_osi_approved: t.Annotated[bool, Alias('isOsiApproved')]
  is_fsf_libre: t.Annotated[bool | None, Alias('isFsfLibre')] = None


@dataclasses.dataclass
class DejaCodeLicense:
  license_text: str
  key: t.Annotated[str, Alias('Key')]
  name: t.Annotated[str, Alias('Name')]
  short_name: t.Annotated[str, Alias('Short Name')]
  category: t.Annotated[str, Alias('Category')]
  license_type: t.Annotated[str, Alias('License type')]
  license_profile: t.Annotated[str, Alias('License profile')]
  license_style: t.Annotated[str, Alias('License style')]
  owner: t.Annotated[str, Alias('Owner')]
  spdx_short_identifier: t.Annotated[str, Alias('SPDX short identifier')]
  keywords: t.Annotated[str, Alias('Keywords')]
  standard_notice: t.Annotated[str | None, Alias('Standard notice')]
  special_obligations: t.Annotated[str | None, Alias('Special obligations')]
  publication_year: t.Annotated[int, Alias('Publication year')]
  urn: t.Annotated[str, Alias('URN')]
  dataspace: t.Annotated[str, Alias('Dataspace')]
  homepage_url: t.Annotated[str, Alias('Homepage URL')]
  text_urls: t.Annotated[str, Alias('Text URLs')]
  osi_url: t.Annotated[str, Alias('OSI URL')]
  faq_url: t.Annotated[str, Alias('FAQ URL')]
  guidance_url: t.Annotated[str | None, Alias('Guidance URL')]
  other_urls: t.Annotated[str | None, Alias('Other URLs')]


def _get_table_value_by_key(soup, key):
  regex = re.compile('\s*' + re.escape(key) + '\s*')
  item = soup.find('span', text=regex)
  if item is None:
    raise ValueError('<span/> for key {!r} not found'.format(key))
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


def get_license_metadata(license_name: str) -> DejaCodeLicense:
  """ Retrives the HTML metadata page for the specified license from the DejaCode website and extracts information
  such as the name, category, license type, standard notice and license text. """

  url = BASE_URL.format(license_name.replace(' ', '-').lower())
  response = requests.get(url)
  response.raise_for_status()
  html = response.text
  soup = bs4.BeautifulSoup(html, 'html.parser')

  # Get the keys that need to be extracted from the dataclass field aliases
  from databind.core.schema import convert_dataclass_to_schema
  from databind.json import load
  schema = convert_dataclass_to_schema(DejaCodeLicense)
  extract_keys = [field.aliases[0] for field in schema.fields.values() if field.aliases]

  data = {}
  for key in extract_keys:
    data[key] = _get_table_value_by_key(soup, key)
  data['Publication year'] = int(data['Publication year'])
  if data['Standard notice']:
    data['Standard notice'] = textwrap.dedent(data['Standard notice'])
  data['license_text'] = _get_license_text(soup)

  return load(data, DejaCodeLicense)


def wrap_license_text(license_text: str, width: int = 79) -> str:
  lines = []
  for raw_line in license_text.split('\n'):
    line = raw_line.split(' ')
    length = sum(map(len, line)) + len(line) - 1
    if length > width:
      words: list[str] = []
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


def get_spdx_licenses() -> dict[str, SpdxLicense]:
  """ Returns a dictionary of all SPDX licenses, keyed by the license ID."""

  import databind.json
  url = 'https://raw.githubusercontent.com/spdx/license-list-data/master/json/licenses.json'
  response = requests.get(url)
  response.raise_for_status()
  licenses = databind.json.load(response.json()['licenses'], list[SpdxLicense], filename=url)
  return {l.license_id: l for l in licenses}


if __name__ == '__main__':
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument("-l", "--list", action="store_true")
  parser.add_argument("license", nargs='?')
  args = parser.parse_args()
  if args.list:
    for key, value in get_spdx_licenses().items():
      print(key, value)
  else:
    print(get_license_metadata(args.license))
