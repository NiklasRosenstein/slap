# Plugins

A lot of Slam's internal functionality is provided through a plugin interface, allowing other tools to extend the
functionality of Slam further.

## Types of plugins

* {@pylink slam.plugins.ApplicationPlugin} &ndash; This is the main type of plugin. Most other types of plugins are registered through an
  application plugin using the `Application.plugins` registry.
* {@pylink slam.plugins.CheckPlugin} &ndash; The type of plugin used by `slam check`.
* {@pylink slam.plugins.ReleasePlugin} &ndash; The type of plugin used by `slam release` to detect version references.
