
from pathlib import Path
from novella.markdown.processor import novella_tag, NovellaTagContext
from novella.novella import Novella


@novella_tag
def cleo_describe(novella: Novella, path: Path, args: str) -> str:
  return "hello from cleo_describe: " + args
