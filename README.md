# pliz

Pliz is a distribution and release management tool for pure Python packages
and mono repositories.

## FAQ

### What is the difference between `datafiles` and `packagedata`?

`datafiles` allows you to install files into the interpreter prefix. It uses
the `data_files` argument in `setuptools.setup()`. Example:

```yaml
package:
  name: mypackage
  # ...
datafiles:
  - src/datafiles:.,file.txt
```

Note that Pliz always prefixes the target path with `data/<package_name>/`.
Thus in order to read a data file called `file.txt` after the package is
installed, you need take that prefix into account:

```python
import os, sys
filename = os.path.join(sys.prefix, 'data', 'mypackage', 'file.txt')
```

To include files into the actual Python package along with your source code,
use the `manifest` option (or manually create a `MANIFEST.in` file). The
`manifest` option accepts a list of lines to write into the manifest file.
Example:

```yaml
package:
  name: mypackage
  # ...
manifest:
- include src/mypackage/data/file.txt
- recursive-include src/mypackage/data/models *.bin
```

Then use the `pkg_resources` module to read the data.

```python
import pkg_resources
print(pkg_resources.resource_string('mypackage', 'data/file.txt'))
```

> You can use `python setup.py sdist` to test if the files are included
> the way you expect them to be.
