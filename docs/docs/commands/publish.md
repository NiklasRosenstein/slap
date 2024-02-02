# `slap publish`

  [Twine]: https://twine.readthedocs.io/en/stable/

This command builds an `sdist` and `wheel` distribution for your project or every project in your mono-repository and
publishes it using [Twine][] (the command has pretty much all the same options). Often you will use this command
immediately after running [`slap release`](release.md) or from a CI job when new tag/release was created.

If you just want to build your package(s) and not actually publish them, add the `-d,--dry` option. To be able to
inspect the resulting distribution files and not loose them to the temporary directory, pass an explicit build
directory using `-b,--build-directory`.

<details><summary>Synopsis</summary>
```
@shell slap publish --help
```
</details>
