# Skills and hooks are linked into ~/.claude, not shipped as a Claude Code plugin

A plugin marketplace in this repo would install, update, and retire the skills and hooks on every
machine without `install.sh`'s links and install record. It is not used, for two reasons. Plugin
hooks load only at session start or `/reload-plugins`, so after a pull removes a hook script every
running session keeps calling it and blocks, while a hook registered in `settings.json` reaches
running sessions through that file's watcher. And the permissions must be merged into the live
`settings.json` either way, so the install machinery would stay. Reopen this once plugins can
carry permissions and running sessions pick up changed plugin hooks.
