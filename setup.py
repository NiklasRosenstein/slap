
from setuptools import setup, find_packages

setup(
  name='pliz',
  version='0.9.0.dev0',
  packages=find_packages('src', exclude=['test*', 'docs*']),
  package_dir={'': 'src'},
  install_requires=['nr.databind', 'nr.collections', 'nr.proxy', 'bs4', 'requests'],
  entry_points={
    'console_scripts': [
      'pliz = pliz.__main__:console_main'
    ]
  }
)
