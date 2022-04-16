from slap.python.pep508 import Pep508Environment


def test__Pep508Environment__sample_markers():
    env = Pep508Environment(
        python_version="3.10",
        python_full_version="3.10.2",
        os_name="posix",
        sys_platform="darwin",
        platform_release="21.3.0",
        platform_system="Darwin",
        platform_machine="arm64",
        platform_python_implementation="CPython",
        implementation_name="cpython",
        implementation_version="3.10.2",
    )

    assert env.evaluate_markers('os_name == "posix"')
    assert not env.evaluate_markers('os_name == "Posix"')

    assert env.evaluate_markers('python_version<"3.11"')
    assert not env.evaluate_markers('python_version<"3.10"')

    assert env.evaluate_markers('(os_name=="nt") or python_version<="3.10"')
    assert not env.evaluate_markers('(os_name=="nt") and python_version<="3.10"')
    assert env.evaluate_markers('(os_name=="posix") and python_version<="3.10"')

    assert env.evaluate_markers(
        '(extra == "docs" or extra == "dev") and ((os_name=="posix") and python_version<="3.10")', {"docs"}
    )
    assert env.evaluate_markers(
        '(extra == "docs" or extra == "dev") and ((os_name=="posix") and python_version<="3.10")', {"dev"}
    )
    assert not env.evaluate_markers(
        '(extra == "docs" or extra == "dev") and ((os_name=="posix") and python_version<="3.10")', {"foobar"}
    )

    # All fields are supposed to be strings
    for key, value in env.as_json().items():
        assert isinstance(value, str)
