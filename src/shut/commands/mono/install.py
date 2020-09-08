
import click
import networkx as nx

from shut.commands.pkg.install import collect_requirements, run_install, split_extras
from shut.model.monorepo import MonorepoModel
from shut.model.requirements import RequirementsList
from . import mono, project


@mono.command()
@click.option('--develop/--no-develop', default=True,
  help='Install in develop mode (default: true)')
@click.option('--extra', type=split_extras, help='Specify one or more extras to install.')
@click.option('-U', '--upgrade', is_flag=True, help='Upgrade all packages (forwarded to pip install).')
@click.option('-q', '--quiet', is_flag=True, help='Quiet install')
@click.option('--pip', help='Override the command to run Pip. Defaults to "python -m pip" or the PIP variable.')
@click.option('--pip-args', help='Additional arguments to pass to Pip.')
@click.option('--dry', is_flag=True, help='Print the Pip command to stdout instead of running it.')
def install(develop, extra, upgrade, quiet, pip, pip_args, dry):
  """
  Install all packages in the monorepo using`python -m pip`.

  The command used to invoke Pip can be overwritten using the `PIP` environment variable.
  """

  monorepo = project.load_or_exit(expect=MonorepoModel)
  graph = monorepo.get_inter_dependencies_graph()
  package_map = {p.name: p for p in project.packages}

  reqs = []
  for package_name in nx.algorithms.dag.topological_sort(graph):
    package = package_map[package_name]
    reqs.append((package.get_directory(), collect_requirements(package, False, extra)))

  run_install(pip, reqs, develop, upgrade, quiet, dry, pip_args)
