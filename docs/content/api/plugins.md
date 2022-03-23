# Plugins

A lot of Clap's internal functionality is provided through a plugin interface, allowing other tools to extend the
functionality of Clap further.

## Types of plugins

* {@pylink clap.plugins.ApplicationPlugin} &ndash; This is the main type of plugin. Most other types of plugins are registered through an
  application plugin using the `Application.plugins` registry.
* {@pylink clap.plugins.CheckPlugin} &ndash; The type of plugin used by `clap check`.
* {@pylink clap.plugins.ReleasePlugin} &ndash; The type of plugin used by `clap release` to detect version references.
