
import os
from pathlib import Path
from slam.application import Application


def main():
  cwd = os.getenv('SLAM_DIR')
  if cwd:
    os.chdir(cwd)
    os.unsetenv('SLAM_DIR')
  Application(Path.cwd())()
