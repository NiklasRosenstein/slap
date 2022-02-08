
import typing as t


def toml_highlight(toml_data: dict[str, t.Any]) -> str:
  import tomli_w
  import pygments, pygments.lexers, pygments.formatters
  return pygments.highlight(
    tomli_w.dumps(toml_data),
    pygments.lexers.get_lexer_by_name('toml'),
    pygments.formatters.get_formatter_by_name('terminal')
  )
