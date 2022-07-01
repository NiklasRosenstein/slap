"""
Scraper for [SPDX][1].

  [1]: https://spdx.org/licenses/
"""

from __future__ import annotations

import dataclasses
import typing as t

import requests
from databind.core.settings import Alias


@dataclasses.dataclass
class SpdxLicense:
    reference: str
    is_deprecated_license_id: t.Annotated[bool, Alias("isDeprecatedLicenseId")]
    details_url: t.Annotated[str, Alias("detailsUrl")]
    reference_number: t.Annotated[int, Alias("referenceNumber")]
    name: str
    license_id: t.Annotated[str, Alias("licenseId")]
    see_also: t.Annotated[list[str], Alias("seeAlso")]
    is_osi_approved: t.Annotated[bool, Alias("isOsiApproved")]
    is_fsf_libre: t.Annotated[bool | None, Alias("isFsfLibre")] = None

    def get_details(self) -> SpdxLicenseDetails:
        import databind.json

        response = requests.get(self.details_url)
        response.raise_for_status()
        return databind.json.load(response.json(), SpdxLicenseDetails)


@dataclasses.dataclass
class SpdxLicenseDetails:
    name: str
    license_id: t.Annotated[str, Alias("licenseId")]
    license_text: t.Annotated[str, Alias("licenseText")]
    license_text_html: t.Annotated[str, Alias("licenseTextHtml")]
    cross_ref: t.Annotated[list[dict[str, t.Any]], Alias("crossRef")]
    see_also: t.Annotated[list[str], Alias("seeAlso")]
    standard_license_template: t.Annotated[str, Alias("standardLicenseTemplate")]
    is_osi_approved: t.Annotated[bool, Alias("isOsiApproved")]
    is_deprecated_license_id: t.Annotated[bool, Alias("isDeprecatedLicenseId")]
    license_comments: t.Annotated[str | None, Alias("licenseComments")] = None
    is_fsf_libre: t.Annotated[bool | None, Alias("isFsfLibre")] = None
    standard_license_header_html: t.Annotated[str | None, Alias("standardLicenseHeaderHtml")] = None
    standard_license_header: t.Annotated[str | None, Alias("standardLicenseHeader")] = None
    standard_license_header_template: t.Annotated[str | None, Alias("standardLicenseHeaderTemplate")] = None
    deprecated_version: t.Annotated[str | None, Alias("deprecatedVersion")] = None


def wrap_license_text(license_text: str, width: int = 79) -> str:
    lines = []
    for raw_line in license_text.split("\n"):
        line = raw_line.split(" ")
        length = sum(map(len, line)) + len(line) - 1
        if length > width:
            words: list[str] = []
            length = -1
            for word in line:
                if length + 1 + len(word) >= width:
                    lines.append(" ".join(words))
                    words = []
                    length = -1
                else:
                    words.append(word)
                    length += len(word) + 1
            if words:
                lines.append(" ".join(words))
        else:
            lines.append(" ".join(line))
    return "\n".join(lines)


def get_spdx_licenses() -> dict[str, SpdxLicense]:
    """Returns a dictionary of all SPDX licenses, keyed by the license ID."""

    import databind.json

    url = "https://raw.githubusercontent.com/spdx/license-list-data/master/json/licenses.json"
    response = requests.get(url)
    response.raise_for_status()
    licenses = databind.json.load(response.json()["licenses"], list[SpdxLicense], filename=url)
    return {line.license_id: line for line in licenses}


def get_spdx_license_details(license_id: str) -> SpdxLicenseDetails:
    """Returns the details for a single SPDX license."""

    import databind.json

    url = f"https://spdx.org/licenses/{license_id}.json"
    response = requests.get(url)
    response.raise_for_status()
    return databind.json.load(response.json(), SpdxLicenseDetails, filename=url)


if __name__ == "__main__":
    import argparse

    from termcolor import colored

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--list", action="store_true")
    parser.add_argument("license", nargs="?")
    parser.add_argument("-w", "--wrap", type=int, default=80)
    args = parser.parse_args()
    if args.list:
        for key, value in sorted(get_spdx_licenses().items()):
            print(f'{colored(key, attrs=["bold"])}: {value.name}')
    elif args.license:
        print(wrap_license_text(get_spdx_license_details(args.license).license_text, args.wrap - 1))
    else:
        parser.error("need an argument")
