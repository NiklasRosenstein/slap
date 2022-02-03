
import typing as t

from nr.util.generic import T


class PluginRegistry(t.Generic[T]):
  """ A registry for plugins of a particular type. """

  def __init__(self) -> None:
    self._plugins: dict[str, T] = {}

  def __contains__(self, plugin_id: t.Any) -> bool:
    return plugin_id in self._plugins

  def __getitem__(self, plugin_id: str) -> T:
    return self._plugins[plugin_id]

  def __len__(self) -> int:
    return len(self._plugins)

  def __iter__(self) -> t.Iterator[str]:
    return iter(self._plugins.iter())

  def register_plugin(self, plugin_id: str, plugin: T) -> None:
    if plugin_id in self._plugins:
      raise ValueError(f'plugin id {plugin_id!r} already registered')
    self._plugins[plugin_id] = plugin
