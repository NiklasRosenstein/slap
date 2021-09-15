
from shut.model.package import PackageModel
from shut.model.requirements import Requirement, VersionSelector


def test_package_is_universal():
  package = PackageModel(name='test', description='')  # type: ignore  # TODO (@NiklasRosenstein): Why does mypy complain about unexpected keyword arguments?

  assert not package.get_python_requirement()
  assert package.is_universal()

  def set_python_requirement(selector):
    req = package.get_python_requirement()
    if req:
      package.requirements.remove(req)
    package.requirements.append(Requirement('python', VersionSelector(selector)))

  set_python_requirement('2.7')
  assert not package.is_universal()

  set_python_requirement('3.4')
  assert not package.is_universal()

  set_python_requirement('>= 3.4')
  assert not package.is_universal()

  set_python_requirement('^2.7 | ^.3.3')
  assert package.is_universal()

  set_python_requirement('>= 2.7 | >= 3.3')
  assert package.is_universal()

  set_python_requirement('~2.7 | ~2.10')
  assert not package.is_universal()

  set_python_requirement('2|3')
  assert package.is_universal()
