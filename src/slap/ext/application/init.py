import datetime
import textwrap
from pathlib import Path

from slap.application import Application, Command, argument, option
from slap.plugins import ApplicationPlugin
from slap.util.external.licenses import get_spdx_license_details, wrap_license_text
from slap.util.vcs import get_git_author

TEMPLATES = {
    "poetry": {
        "pyproject.toml": """
            [build-system]
            requires = ["poetry-core"]
            build-backend = "poetry.core.masonry.api"

            [tool.poetry]
            name = "{name}"
            version = "0.1.0"
            description = ""
            authors = ["{author_name} <{author_email}>"]
            license = "{license}"
            readme = "readme.md"
            packages = [{{ include = "{path}", from = "src" }}]
            classifiers = []
            keywords = []

            [tool.poetry.urls]
            # "Bug Tracker" = ""
            # Documentation = ""
            # Homepage = ""
            # Repository = ""

            [tool.poetry.dependencies]
            python = "^3.6"

            [tool.poetry.dev-dependencies]
            black = "*"
            flake8 = "*"
            isort = "*"
            mypy = "*"
            pytest = "*"

            [tool.slap]
            typed = true

            [tool.slap.test]
            check = "slap check"
            mypy = "dmypy run src/"
            pytest = "pytest tests/ -vv"
            black = "black --check src/ tests/"
            isort = "isort --check-only src/ tests/"
            flake8 = "flake8 src/ tests/"

            [tool.slap.run]
            fmt = "black src/ tests/ && isort src/ tests/"

            [tool.mypy]
            python_version = "3.6"
            explicit_package_bases = true
            mypy_path = ["src"]
            namespace_packages = true
            pretty = true
            show_error_codes = true
            show_error_context = true
            strict = true
            warn_no_return = true
            warn_redundant_casts = true
            warn_unreachable = true
            warn_unused_ignores = true

            [tool.isort]
            profile = "black"
            line_length = 120
            combine_as_imports = true

            [tool.black]
            line-length = 120
        """,
        "LICENSE": "",
        "readme.md": """
            # {name}

        """,
        ".flake8": """
            [flake8]
            max-line-length = 120
            # Black can yield formatted code that triggers these Flake8 warnings.
            ignore=
                # line break before binary operator
                W503,
                # line break after binary operator
                W504,
        """,
        ".gitignore": """
            /.vscode
            /dist
            /build
            .venv/
            *.egg-info/
            __pycache__/
            poetry.lock
        """,
        "src/{path}/__init__.py": """
            __version__ = "0.1.0"
        """,
        "tests/test_import.py": """
            def test_import():
                exec("from {dotted_name} import *")
    """,
        "src/{path}/py.typed": "",
    },
    "github": {
        ".github/workflows/python-package.yml": """
            name: Python application

            on:
              push: {{ branches: [ develop ], tags: [ "*" ] }}
              pull_request: {{ branches: [ develop ] }}

            jobs:
              test:
                runs-on: ubuntu-latest
                strategy:
                  fail-fast: false
                  matrix:
                    python-version: [ "3.6", "3.7", "3.8", "3.9", "3.10", "3.x" ]
                steps:
                - uses: actions/checkout@v2
                - uses: python-slap/slap-cli@gha/install/v1
                - uses: actions/setup-python@v2
                  with: {{ python-version: "${{{{ matrix.python-version }}}}" }}
                - run: slap install -vv --no-venv-check
                - run: slap test

              update-changelog:
                runs-on: ubuntu-latest
                if: github.event_name == 'pull_request'
                steps:
                  - uses: actions/checkout@v2
                  - uses: python-slap/slap-cli@gha/changelog/update/v1
    """,
    },
}


class InitCommandPlugin(ApplicationPlugin, Command):
    """Bootstrap some files for a Python project.

    Currently available templates:

    1. <info>poetry</info>
    """

    app: Application

    name = "init"
    arguments = [
        argument(
            "directory",
            description="The directory in which to create the generated files. If not specified, a new directory with "
            "the name specified via the <opt>--name</opt> option is created.",
            optional=True,
        )
    ]
    options = [
        option(
            "--name",
            description="The name of the Python package.",
            flag=False,
        ),
        option(
            "--license",
            description="The package license.",
            flag=False,
            default="MIT",
        ),
        option(
            "--template",
            "-t",
            description="The template to use.",
            flag=False,
            default="poetry",
        ),
        option(
            "--overwrite",
            "-f",
            description="Overwrite files.",
        ),
        option(
            "--dry",
            "-d",
            description="Dont actually write files.",
        ),
        option(
            "--as-markdown",
            description="Render the content as Markdown (uses by the Slap docs)",
        ),
    ]

    def load_configuration(self, app: Application) -> None:
        return None

    def activate(self, app: Application, config: None) -> None:
        self.app = app
        app.cleo.add(self)

    def handle(self) -> int:
        from nr.util.optional import Optional

        template = self.option("template")
        if template not in TEMPLATES:
            self.line_error(f'error: template "{template}" does not exist', "error")
            return 1

        author = get_git_author()
        name = self.option("name")
        directory = (
            Optional(self.argument("directory"))
            .map(Path)
            .map(lambda v: v or (name.replace(".", "-") if name else None))
            .or_else_get(Path.cwd)
        )

        scope = {
            "license": self.option("license"),
            "year": datetime.date.today().year,
            "author_name": author.name if author and author.name else "Unknown",
            "author_email": author.email if author and author.email else "me@unknown.org",
        }
        if self.option("name"):
            scope.update(
                {
                    "name": self.option("name"),
                    "dotted_name": self.option("name").replace("-", "_"),
                    "path": self.option("name").replace(".", "/").replace("-", "_"),
                    "package": self.option("name").replace(".", "_").replace("-", "_"),
                }
            )
        for filename, content in TEMPLATES[template].items():
            if filename == "LICENSE":
                content = get_spdx_license_details(self.option("license")).license_text
                content = wrap_license_text(content).replace("<year>", str(scope["year"]))
                content = wrap_license_text(content).replace("<copyright holders>", scope["author_name"])
            else:
                filename = filename.format(**scope)
                content = textwrap.dedent(content.format(**scope)).strip()
                if content:
                    content += "\n"

            path = directory / filename

            if self.option("as-markdown"):
                print(f'```{path.suffix[1:]} title="{path}"')
                print(content, "    ")
                print("```\n\n")
                continue

            if path.exists() and not self.option("overwrite"):
                self.line(f"skip <info>{path}</info> (already exists)")
                continue

            if not self.option("dry") and not self.option("as-markdown"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)

            self.line(f"write <info>{path}</info>")

        return 0
