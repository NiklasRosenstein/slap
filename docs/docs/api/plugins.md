# Plugins

A lot of Slap's internal functionality is provided through a plugin interface, allowing other tools to extend the
functionality of Slap further.

## Types of plugins

* [slap.plugins.ApplicationPlugin][] &ndash; This is the main type of plugin. Most other types of plugins are registered through an
  application plugin using the `Application.plugins` registry.
* [slap.plugins.CheckPlugin][] &ndash; The type of plugin used by `slap check`.
* [slap.plugins.ReleasePlugin][] &ndash; The type of plugin used by `slap release` to detect version references.
