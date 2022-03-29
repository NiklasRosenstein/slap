# Add

Add a Python package to the dependencies of your package. Support for this command depends on the project handler
that supports your project. Currently supported natively for Poetry and Flit projects.

__Example__:

    $ git diff
    $ slap add httpx
    Installing httpx
    Adding httpx ^0.22.0
    $ git diff
    diff --git a/pyproject.toml b/pyproject.toml
    index 4763fd1..c0652b5 100644
    --- a/pyproject.toml
    +++ b/pyproject.toml
    @@ -23,6 +23,7 @@ keywords = []
    python = "^3.7"
    databind = "^2.0.0a2"
    prometheus-client = "0.13.1"
    +httpx = "^0.22.0"

    [tool.poetry.dev-dependencies]
    mypy = "*"
