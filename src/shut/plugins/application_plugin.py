
import abc
import typing as t

if t.TYPE_CHECKING:
  from shut.console.application import Application

ENTRYPOINT = 'shut.plugins.application'


class ApplicationPlugin(abc.ABC):

  @abc.abstractmethod
  def activate(self, app: 'Application') -> None:
    ...
