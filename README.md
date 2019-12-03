# pliz

Pliz is a distribution and release management tool for pure Python packages
and mono repositories.

## FAQ

### What is the difference between `datafiles` and `packagedata`?

`datafiles` allows you to install files into the interpreter prefix. It uses
the `data_files` argument in `setuptools.setup()`. Note however that Pliz
always prefixes the target path with `data/<package_name>/`. Thus in order to
read a data file called `file.txt` after the package is installed, you need
take that prefix into account:

```python
import os, sys
filename = os.path.join(sys.prefix, 'data', '<YOUR_PACKAGE_NAME>', 'file.txt')
```

`packagedata` uses the `package_data` argument in `setuptools.setup()`. It
only works with data that is actually contained inside the package's source
directory. These files must be retrieved with the `pkg_resources` module.
