# Codex capability profiles

Codex 0.163.0 exposes session capability controls through its app-server. The current `sm-plugin` integration starts one private Unix-socket app-server for each launch, registers the selected skill roots, then connects the native TUI with `--remote`.

The additive path uses:

```text
skills/extraRoots/set
```

The exclusive path adds session configuration before the server starts:

```toml
[features]
plugins = false

[skills.bundled]
enabled = false

[[skills.config]]
path = "/path/to/skill/SKILL.md"
enabled = false
```

`sm-plugin` first reads the native skill catalog. It disables the discovered user and project skill paths, disables plugins and bundled skills, adds the selected bundle as an extra root, and re-enables the selected bundle paths. It then calls `skills/list` and compares the enabled paths with the bundle manifest before reporting success.

Use the current integration with:

```sh
sm-plugin launch codex Research --mode exclusive
sm-plugin verify codex Research --mode exclusive
```

Codex keeps native authentication, model settings, and session storage. The app-server itself is private to the launch, so different launches can use different skill roots without rewriting a shared `config.toml`.

The exclusive boundary is about skills and plugin activation. Codex's session API does not provide a general logical selector that replaces every installed capability. `skills/extraRoots/set` adds roots, and `skills.config` disables known skills. The adapter must verify the final catalog and fail if it does not match the requested profile.

The Codex adapter should keep the following data separate:

- The `sm` bundle membership snapshot.
- The temporary app-server configuration.
- The native account and model configuration.
- The verification result from `skills/list`.

Do not share one app-server between profiles. The extra-root setting is process-scoped in the current integration. A shared server would allow one profile to replace another profile's roots.
