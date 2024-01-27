""" Tools for URL handling. """

from __future__ import annotations

import dataclasses
import urllib.parse


@dataclasses.dataclass
class Url:
    """Helper to represent the components of a URL, including first class support for username, password, host
    and port."""

    scheme: str = ""
    hostname: str = ""
    path: str = ""
    params: str = ""
    query: str = ""
    fragment: str = ""

    username: str | None = None
    password: str | None = None
    port: int | None = None

    def __str__(self) -> str:
        return urllib.parse.urlunparse((self.scheme, self.netloc, self.path, self.params, self.query, self.fragment))

    @property
    def netloc(self) -> str:
        """Returns the entire network location with auth and port."""

        auth = self.auth
        if auth:
            return f"{self.auth}@{self.netloc_no_auth}"

        return self.netloc_no_auth

    @property
    def auth(self) -> str | None:
        """Returns just the auth part of the network location."""

        if self.username or self.password:
            return f'{urllib.parse.quote(self.username or "")}:{urllib.parse.quote(self.password or "")}'

        return None

    @property
    def netloc_no_auth(self) -> str:
        """Returns the network location without the auth part."""

        if self.port is None:
            return self.hostname

        return f"{self.hostname}:{self.port}"

    @staticmethod
    def of(url: str) -> Url:
        """Parses the *url* string into its parts.

        Raises:
          ValueError: If an invalid URL is passed (for example if the port number cannot be parsed to an integer).
        """
        parsed = urllib.parse.urlparse(url)
        return Url(
            scheme=parsed.scheme,
            hostname=parsed.hostname or "",
            path=parsed.path,
            params=parsed.params,
            query=parsed.query,
            fragment=parsed.fragment,
            username=parsed.username,
            password=parsed.password,
            port=parsed.port,
        )
