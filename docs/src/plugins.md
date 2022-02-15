# Plugins

A lot of Slam's internal functionality is provided through a plugin interface, allowing other tools to extend the
functionality of Slam further.

## Types of plugins

* `ApplicationPlugin` &ndash; This is the main type of plugin. Most other types of plugins are registered through an
  application plugin using the `Application.plugins` registry.
* `CheckPlugin` &ndash; The type of plugin used by `slam check`.
* `ReleasePlugin` &ndash; The type of plugin used by `slam release` to detect version references.
* `RemoteDetectorPlugin` &ndash; A type of plugin that is intended to automatically detect the type of remote repository
  used in a project and return an appropriate `ChangelogValidator` for use by the `slam log` commands.
