import datetime
import textwrap
from pathlib import Path
from typing import Iterable

from slap.application import Application, Command, argument, option
from slap.plugins import ApplicationPlugin
from slap.util.external.licenses import get_spdx_license_details, wrap_license_text
from slap.util.vcs import get_git_author

TEMPLATES = ["poetry", "github"]


def load_template(name: str) -> Iterable[tuple[str, str]]:
    """
    Loads a template, iterating over all its files.
    """

    import slap

    path = Path(slap.__file__).parent / "templates" / name
    for filename in path.glob("**/*"):
        if filename.is_dir():
            continue
        if "__pycache__" in filename.parts:
            continue
        yield str(filename.relative_to(path)), filename.read_text()


class InitCommandPlugin(Command, ApplicationPlugin):
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

    def __init__(self, app: Application) -> None:
        Command.__init__(self)
        ApplicationPlugin.__init__(self, app)

    def load_configuration(self, app: Application) -> None:
        return None

    def activate(self, app: Application, config: None) -> None:
        self.app = app
        app.cleo.add(self)

    def handle(self) -> int:
        from nr.stream import Optional

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
        for filename, content in load_template(template):
            if filename == "LICENSE":
                if self.option("license") in ("null", "none"):
                    continue
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
