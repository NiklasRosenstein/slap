import platform
import sys

from slap.python.environment import PythonEnvironment


def test__PythonEnvironment__with_current_python_instance():
    environment = PythonEnvironment.of(sys.executable)
    assert environment.executable == sys.executable
    assert environment.version == sys.version
    assert environment.platform == platform.platform()
    assert environment.prefix == sys.prefix
    assert environment.base_prefix == getattr(sys, "base_prefix", None)
    assert environment.real_prefix == getattr(sys, "real_prefix", None)
    assert environment.has_importlib_metadata()
    assert environment.get_distribution("setuptools") is not None
