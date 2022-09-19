from pathlib import Path

import pytest

from slap.python.dependency import (
    GitDependency,
    MultiDependency,
    PathDependency,
    PypiDependency,
    UrlDependency,
    VersionSpec,
    parse_dependency_config,
    parse_dependency_string,
    split_package_name_with_extras,
)


def test__split_package_name_with_extras__good_input():
    assert split_package_name_with_extras("kek") == ("kek", None)
    assert split_package_name_with_extras("kek[docs]") == ("kek", ["docs"])
    assert split_package_name_with_extras("kek[docs, internal]") == ("kek", ["docs", "internal"])
    assert split_package_name_with_extras(" bruv-kek    [ docs , internal] ") == ("bruv-kek", ["docs", "internal"])


def test__split_package_name_with_extras__bad_input():
    with pytest.raises(ValueError):
        split_package_name_with_extras("kek[")
    with pytest.raises(ValueError):
        split_package_name_with_extras("kek[[docs, internal]]")
    with pytest.raises(ValueError):
        split_package_name_with_extras("kek[docs, in]ternal]")
    with pytest.raises(ValueError):
        split_package_name_with_extras("kek][docs]")


def test__parse_dependency_string__can_parse_pypi_dependency():
    assert parse_dependency_string("kek") == PypiDependency("kek", VersionSpec("*"))
    assert parse_dependency_string("kek *") == PypiDependency("kek", VersionSpec("*"))
    assert parse_dependency_string("kek>=1.0.0,<2.0.0") == PypiDependency("kek", VersionSpec(">=1.0.0,<2.0.0"))
    assert parse_dependency_string("kek ^1.0.0") == PypiDependency("kek", VersionSpec("^1.0.0"))
    assert parse_dependency_string("kek [docs,  internal] ^1.0.0 --hash=sha1:123456") == PypiDependency(
        "kek", VersionSpec("^1.0.0"), extras=["docs", "internal"], hashes=["sha1:123456"]
    )
    assert parse_dependency_string(
        'kek [docs,  internal] ^1.0.0; python_version="<2.7" --hash=sha1:123456'
    ) == PypiDependency(
        "kek",
        VersionSpec("^1.0.0"),
        extras=["docs", "internal"],
        markers='python_version="<2.7"',
        hashes=["sha1:123456"],
    )


def test__parse_dependency_string__can_parse_git_dependency():
    assert parse_dependency_string('kek@git+https://github.com/kek/kek.git; os_name="nt"') == GitDependency(
        "kek", "https://github.com/kek/kek.git", markers='os_name="nt"'
    )
    assert parse_dependency_string("kek[docs] @ git+https://github.com/kek/kek.git") == GitDependency(
        "kek", "https://github.com/kek/kek.git", extras=["docs"]
    )
    assert parse_dependency_string("kek[docs] @ git+https://github.com/kek/kek.git#branch=develop") == GitDependency(
        "kek", "https://github.com/kek/kek.git", branch="develop", extras=["docs"]
    )
    with pytest.raises(ValueError):
        parse_dependency_string("kek[docs] >=1.0 @ git+https://github.com/kek/kek.git#branch=develop")


def test__parse_dependency_string__can_parse_url_dependency():
    assert parse_dependency_string("kek @ https://blog.org/kek-1.2.1.tar.gz#sha1=123456&sha1=654321") == UrlDependency(
        "kek", "https://blog.org/kek-1.2.1.tar.gz", hashes=["sha1:123456", "sha1:654321"]
    )
    assert parse_dependency_string(
        "kek[docs] @ https://blog.org/kek-1.2.1.tar.gz#sha1=123456 --hash=sha1:654321"
    ) == UrlDependency(
        "kek", "https://blog.org/kek-1.2.1.tar.gz", extras=["docs"], hashes=["sha1:654321", "sha1:123456"]
    )


def test__parse_dependency_string__can_parse_path_dependency():
    assert parse_dependency_string("kek @ ../../kek") == PathDependency("kek", Path("../../kek"))
    assert parse_dependency_string("kek @ ./kek") == PathDependency("kek", Path("./kek"))
    assert parse_dependency_string("kek @ /git/kek") == PathDependency("kek", Path("/git/kek"))
    with pytest.raises(ValueError):
        parse_dependency_string("kek @ kek/kek")


def test__parse_dependency_config__various_configurations():
    assert parse_dependency_config("kek", "*") == PypiDependency("kek", VersionSpec("*"))
    assert parse_dependency_config("kek", "1.0.0") == PypiDependency("kek", VersionSpec("1.0.0"))
    assert parse_dependency_config("kek", {"url": "https://blob.org/kek-1.2.1.tar.gz"}) == UrlDependency(
        "kek", "https://blob.org/kek-1.2.1.tar.gz"
    )
    assert parse_dependency_config("kek", {"git": "https://github.com/kek/kek", "branch": "develop"}) == GitDependency(
        "kek", "https://github.com/kek/kek", branch="develop"
    )
    assert parse_dependency_config(
        "kek",
        [
            "",
            'git+https://github.com/foo/foo.git; python_version=">=2.7,<3.3"',
            {"version": "^1.2.1", "python": ">=3.7"},
            {"url": "https://a.b"},
            {"git": "https://a.git"},
        ],
    ) == MultiDependency(
        "kek",
        [
            PypiDependency("kek", VersionSpec("*")),
            GitDependency("kek", "https://github.com/foo/foo.git", markers='python_version=">=2.7,<3.3"'),
            PypiDependency("kek", VersionSpec("^1.2.1"), python=VersionSpec(">=3.7")),
            UrlDependency("kek", "https://a.b"),
            GitDependency("kek", "https://a.git"),
        ],
    )
    assert parse_dependency_config("foo", "git+https://github.com/foo/foo.git") == GitDependency(
        "foo", "https://github.com/foo/foo.git"
    )


def test__VersionSpec__can_take_empty_string():
    assert VersionSpec("*").to_pep_508() == ""
    assert not VersionSpec("*")


def test__VersionSpec__can_take_wildcard():
    assert VersionSpec("*").to_pep_508() == ""
    assert VersionSpec("*") == VersionSpec("*")


def test__VersionSpec__can_take_pep_508_spec():
    assert VersionSpec(">=1.0.0,<1.1.0").to_pep_508() == ">=1.0.0,<1.1.0"


def test__VersionSpec__can_take_semver_spec():
    assert VersionSpec("^0.1.0").to_pep_508() == ">=0.1.0,<0.2.0"
    assert VersionSpec("^1.1.0").to_pep_508() == ">=1.1.0,<2.0.0"
    assert VersionSpec("~0.1.0").to_pep_508() == ">=0.1.0,<0.2.0"
    assert VersionSpec("~1.1.0").to_pep_508() == ">=1.1.0,<1.2.0"


@pytest.mark.skip("Detecting invalid PEP 508 selectors is currently not supported")
def test__VersionSpec__throws_on_invalid_pep_508_spec():
    assert VersionSpec(">=1.0.0,<1.1.x")


def test__PypiDependency__parse():
    assert PypiDependency.parse("foo") == PypiDependency("foo", VersionSpec("*"))
    assert PypiDependency.parse("foo ^1.0.0") == PypiDependency("foo", VersionSpec("^1.0.0"))
    assert PypiDependency.parse('foo ^1.0.0; platform_system="Linux"') == PypiDependency(
        "foo", VersionSpec("^1.0.0"), markers='platform_system="Linux"'
    )
    assert PypiDependency.parse("PySocks !=1.5.7,<2.0,>=1.5.6 ; extra == 'socks'") == PypiDependency(
        "PySocks", VersionSpec("!=1.5.7,<2.0,>=1.5.6"), markers="extra == 'socks'"
    )

    # TODO (@NiklasRosenstein): This is actually a bad example and we should start raising an error for it.
    assert PypiDependency.parse("foo 1.0.0") == PypiDependency("foo 1.0.0", VersionSpec("*"))
