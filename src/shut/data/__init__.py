
import pkg_resources
import typing as t
from mako.template import Template  # type: ignore


def load_string(relative_path: str, encoding: t.Optional[str] = None) -> str:
  # NOTE (@NiklasRosenstein): Replace CRLF with LF to simulate universal mode file open.
  #                           See also https://github.com/NiklasRosenstein/shut/issues/17
  return pkg_resources.resource_string(__name__, relative_path).decode(encoding or 'utf-8').replace('\r\n', '\n')


def render_mako_template(fp: t.TextIO, template_string: str, template_vars: t.Mapping[str, t.Any]) -> None:
  fp.write(Template(template_string).render(**template_vars).rstrip())
  fp.write('\n')
