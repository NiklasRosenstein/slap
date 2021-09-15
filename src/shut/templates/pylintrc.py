
import dataclasses
from shut.data import load_string
from shut.model import AbstractProjectModel, PackageModel
from shut.renderers import Renderer
from shut.utils.io.virtual import VirtualFiles


@dataclasses.dataclass
class PylintRcTemplate(Renderer[AbstractProjectModel]):

  #: The name of the pylintrc template to use. Currently available is only `shut`.
  use: str

  #: The filename to render the template to. Defaults to `.pylintrc`.
  output: str = '.pylintrc'

  def get_files(self, files: VirtualFiles, obj: AbstractProjectModel) -> None:
    if not isinstance(obj, PackageModel):
      raise RuntimeError(f'pylintrc template is only valid for package.yml')
    files.add_static(self.output, load_string(f'templates/pylintrc-{self.use}.ini'))
