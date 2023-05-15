import contextlib
import tempfile
from pathlib import Path
from typing import Iterable

import build
import build.env

from slap.application import Application, Command, option
from slap.install.installer import PipInstaller
from slap.plugins import ApplicationPlugin


def flatten(it: Iterable[Iterable[str]]) -> Iterable[str]:
    for item in it:
        yield from item


class PublishCommandPlugin(Command, ApplicationPlugin):
    """A wrapper to publish the Python project to a repository such as PyPI.

    Uses the PEP 517 build system defined in the <code>pyproject.toml</code> to build
    packages and then uploads them with Twine. Note that it currently expects the build
    backend to be installed already.

    The command-line options are almost identical to the <code>twine upload</code> command.

    Note: You can combine the `-d` and `-b` options to effectively perform a build, storing
    the artifacts into the specified directory but not publishing them.
    """

    app: Application

    name = "publish"
    options = [
        option(
            "python",
            flag=False,
            description="use this Python executable to build the distribution but do not automatically install build "
            "requirements into it; if not specified a temporary build environment is created",
        ),
        option("repository", "r", flag=False, default="pypi"),
        option("repository-url", flag=False),
        option("sign", "s"),
        option("sign-with", flag=False),
        option("identity", "i", flag=False),
        option("username", "u", flag=False),
        option("password", "p", flag=False),
        option("non-interactive"),
        option("comment", "c", flag=False),
        option("config-file", flag=False, default="~/.pypirc"),
        option("skip-existing"),
        option("cert", flag=False),
        option("client-cert", flag=False),
        # option("verbose"),
        option("disable-progress-bar"),
        option("dry", "d"),
        option("build-directory", "b", flag=False),
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
        from twine.commands.upload import upload
        from twine.settings import Settings

        distributions: list[Path] = []

        with contextlib.ExitStack() as stack:
            build_dir = self.option("build-directory")
            if build_dir is None:
                build_dir = stack.enter_context(tempfile.TemporaryDirectory())

            executable = self.option("python")
            if not executable:
                isolated_env = stack.enter_context(build.env.IsolatedEnvBuilder())
                executable = isolated_env.executable
            else:
                isolated_env = None

            for project in self.app.get_target_projects():
                if isolated_env:
                    isolated_env.install(
                        list(flatten(PipInstaller.dependency_to_pip_arguments(x) for x in project.dependencies().build))
                    )
                if not project.is_python_project:
                    continue

                self.line(f"Build <info>{project.dist_name()}</info>")
                builder = build.ProjectBuilder(project.directory, executable)

                sdist = Path(builder.build("sdist", build_dir))
                self.line(f"  <comment>{sdist.name}</comment>")
                wheel = Path(builder.build("wheel", build_dir))
                self.line(f"  <comment>{wheel.name}</comment>")

                distributions += [sdist, wheel]

            if not self.option("dry"):
                self.line("Publishing")
                kwargs = {option.name.replace("-", "_"): self.option(option.name) for option in self.options}
                kwargs["repository_name"] = kwargs.pop("repository")
                settings = Settings(**kwargs)
                upload(settings, [str(d) for d in distributions])

        return 0
