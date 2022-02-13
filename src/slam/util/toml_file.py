
""" Represents a mutable TOML configuration file in memory. """

import typing as t
from pathlib import Path

from nr.util.generic import T


class TomlFile(t.MutableMapping[str, t.Any]):

  def __init__(self, path: Path, data: dict[str, t.Any] | None = None) -> None:
    self._path = path
    self._data: dict[str, t.Any] | None = data

  def __repr__(self) -> str:
    return f'TomlConfig(path="{self.path}")'

  def __bool__(self) -> bool:
    return self._data is not None or self.exists()

  def __len__(self) -> int:
    return len(self.load())

  def __iter__(self) -> t.Iterator[str]:
    return iter(self.load())

  def __delitem__(self, key: str) -> None:
    del self.load()[key]

  def __getitem__(self, key: str) -> t.Any:
    return self.load()[key]

  def __setitem__(self, key: str, value: t.Any) -> None:
    self.load()[key] = value

  def exists(self) -> bool:
    return self._path.is_file()

  def load(self, force_reload: bool = False) -> dict[str, t.Any]:
    import tomli
    if self._data is None or force_reload:
      with self._path.open('rb') as fp:
        self._data = tomli.load(fp)
    return self._data

  def save(self) -> None:
    import tomli_w
    if self._data is None:
      raise RuntimeError('TomlDocument is empty, call load() or value(data)')
    with self._path.open('wb') as fp:
      tomli_w.dump(self._data, fp)

  @t.overload
  def value(self) -> dict[str, t.Any]: ...

  @t.overload
  def value(self, data: dict[str, t.Any]) -> None: ...

  def value(self, data: dict[str, t.Any] | None = None) -> dict[str, t.Any] | None:
    if data is None:
      return self.load()
    else:
      self._data = data
      return None

  def value_or(self, default: T) -> dict[str, t.Any] | T:
    if self._data is not None:
      return self._data
    if self.exists():
      return self.load()
    return default

  @property
  def path(self) -> Path:
    return self._path
