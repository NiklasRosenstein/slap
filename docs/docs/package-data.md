# Package Data

There are two methods in which additional files can be shipped alongside a
Python package: "data files" and "package data". While files from the former
will be copied into a folder relative to `sys.prefix`, files from the latter
will be installed alongside the package and should be accessed with the
`pkg_resources` module.

Using "data files" usually requires some more effort to make it work with an
editable installation of your package during development (detecting that your
package is currently installed in editable mode and looking for the files in
a different location), thus using "package data" is usually the preferred
method. However if your additional files contain binaries that need to be
present on the file system, "data files" is the better bet.

"Data files" are configured with a special option called `datafiles` which
consists of alist of strings that define which files are to be copied to
what location inside `sys.prefix` as well as patterns for the files to copy.
The syntax is `<src>[:<dst>],<pattern>,<pattern>...`.

```yaml
datafiles:
  - src/datafiles,file.txt
  - src/datafiles:data,!file.txt
```

> Data files are always prefixed with `data/<packagename>`, thus to access the
> file at runtime you must add that to the path like this:
>
> ```py
> os.path.join(sys.prefix, 'data', 'mypackage', 'file.txt')
> ```

"Package files" on the other hand can be included by simply specifying them
in the `MANIFEST.in` file.

```yaml
manifest:
- include src/mypackage/data/file.txt
- recursive-include src/mypackage/data/models *.bin
```

> Tip: You can use the `shore build` command to produce a distribution archive
> of your package, which you can inspect to ensure the (package) data files
> are included as expected.
