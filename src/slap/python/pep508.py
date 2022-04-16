# We want to be at least Python 3.6 compatible, so instead of __future__.annotations we use string
# type hints and the typing module.

import ast
import functools
import operator
import typing as t

if t.TYPE_CHECKING:
    # NOTE (@NiklasRosenstein): For when we check the file individually
    from slap.python.dependency import Dependency  # type: ignore[import]


class Pep508Environment:
    """Contains the variables for evaluating PEP 508 environment markers."""

    def __init__(
        self,
        python_version: str,
        python_full_version: str,
        os_name: str,
        sys_platform: str,
        platform_release: str,
        platform_system: str,
        platform_machine: str,
        platform_python_implementation: str,
        implementation_name: str,
        implementation_version: str,
    ) -> None:
        self.python_version = python_version
        self.python_full_version = python_full_version
        self.os_name = os_name
        self.sys_platform = sys_platform
        self.platform_release = platform_release
        self.platform_system = platform_system
        self.platform_machine = platform_machine
        self.platform_python_implementation = platform_python_implementation
        self.implementation_name = implementation_name
        self.implementation_version = implementation_version

    def __repr__(self) -> str:
        args = ", ".join([f"{k}={v!r}" for k, v in self.as_json().items()])
        return f"{type(self).__name__}({args})"

    @staticmethod
    def current() -> "Pep508Environment":
        """Returns a #Pep508Environment for the current Python interpreter."""

        import os
        import platform
        import sys

        # From PEP 508
        def format_full_version(info):
            version = "{0.major}.{0.minor}.{0.micro}".format(info)
            kind = info.releaselevel
            if kind != "final":
                version += kind[0] + str(info.serial)
            return version

        return Pep508Environment(
            python_version=".".join(platform.python_version_tuple()[:2]),
            python_full_version=platform.python_version(),
            os_name=os.name,
            sys_platform=sys.platform,
            platform_release=platform.release(),
            platform_system=platform.system(),
            platform_machine=platform.machine(),
            platform_python_implementation=platform.python_implementation(),
            implementation_name=sys.implementation.name,
            implementation_version=format_full_version(sys.implementation.version),
        )

    def as_json(self) -> t.Dict[str, str]:
        return dict(vars(self))

    def evaluate_markers(
        self, markers: str, extras: t.Optional[t.Set[str]] = None, source: t.Optional[str] = None
    ) -> bool:
        """Evaluate a PEP 508 environment marker.

        Args:
          markers: The environment markers expression that is to be evaluated.
          extras: A set of extras that the `extra` marker returns true for if compared against. If this argument
            is set to `None`, using the `extra` marker in *markers* is an error.
          source: A string that is used as the filename when parsing the *markers* with #ast.parse(). If the syntax
            is invalid, this value will be included in the error message. If not specified, falls back to `<string>`.
        """

        scope = self.as_json()

        if extras is not None:

            class ExtrasEq:
                def __repr__(self) -> str:
                    return f"ExtrasEq({extras!r})"

                def __eq__(self, other) -> bool:
                    if isinstance(other, str):
                        assert extras is not None
                        return other in extras
                    return False

            scope["extra"] = t.cast(str, ExtrasEq())

        try:
            return _eval_environment_marker_ast(ast.parse(markers, filename=source or "<string>", mode="eval"), scope)
        except (ValueError, KeyError) as exc:
            raise ValueError(f"invalid environment marker string: {markers!r}\n  hint: {exc}")


def _eval_environment_marker_ast(node: ast.AST, scope: t.Dict[str, t.Any]) -> bool:
    """Evaluates an environment marker AST using the given *scope*. This is safer than using #eval()
    to avoid arbitrary code execution."""

    if isinstance(node, ast.Expression):
        return _eval_environment_marker_ast(node.body, scope)

    if isinstance(node, ast.BoolOp):
        op, initial = {
            ast.And: (operator.and_, True),
            ast.Or: (operator.or_, False),
        }[type(node.op)]
        return functools.reduce(lambda a, b: op(a, _eval_environment_marker_ast(b, scope)), node.values, initial)

    elif isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise ValueError("multiple comparators are not supported in environment markers")
        op = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
        }[type(node.ops[0])]
        return op(
            _eval_environment_markers_ast_value(node.left, scope),
            _eval_environment_markers_ast_value(node.comparators[0], scope),
        )

    raise ValueError(f"Node of type {type(node).__name__!r} not supported in environment markers")


def _eval_environment_markers_ast_value(node: ast.expr, scope: t.Dict[str, t.Any]) -> t.Any:
    """Resolve the value of an AST expression from the given *scope*."""

    if isinstance(node, ast.Name):
        try:
            return scope[node.id]
        except KeyError:
            raise ValueError(f"Marker {node.id!r} is not available in this context")

    elif isinstance(node, ast.Constant):
        return node.value

    raise ValueError(f"Node of type {type(node).__name__!r} not supported in environment markers")


def filter_dependencies(
    dependencies: t.Iterable["Dependency"], env: Pep508Environment, extras: t.Optional[t.Set[str]]
) -> t.List["Dependency"]:
    """Filters a collection of dependencies according to their environment markers and Python requirements."""

    return [dependency for dependency in dependencies if test_dependency(dependency, env, extras)]


def test_dependency(dependency: "Dependency", env: Pep508Environment, extras: t.Optional[t.Set[str]]) -> bool:
    """Tests if the *dependency* should be included given the current environment and extras."""

    if dependency.python and not dependency.python.accepts(env.python_version):
        return False
    return not dependency.markers or env.evaluate_markers(dependency.markers, extras)


if __name__ == "__main__":
    print(Pep508Environment.current())
