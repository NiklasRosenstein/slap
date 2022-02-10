
from pathlib import Path
from novella.actions.process_markdown.api import novella_tag
from novella.novella import Novella


@novella_tag
def cleo_describe(novella: Novella, path: Path, args: str) -> str:
  return "hello from cleo_describe: " + args
