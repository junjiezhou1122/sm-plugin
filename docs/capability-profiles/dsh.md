# dsh capability profiles

dsh 0.2.1-rc.2 already has a native profile system. A profile is an ordered tree of plugin bundles and user patch layers. The current profiles live under [~/.dsh/profiles](/Users/junjie/.dsh/profiles).

A profile directory normally contains:

```text
package.json
cordis.yml
cordis.patch.yml
```

`package.json` declares the profile's bundle list. `cordis.yml` is the profile root. `cordis.patch.yml` is the persistent user patch applied after the bundle layers. The launcher accepts one or more temporary patch overlays:

```sh
dsh --profile web --patch /tmp/research.patch.yml
```

Use these commands to inspect the composed result without starting a session:

```sh
dsh --profile web --dump-config
dsh --profile web --dump-default-config
dsh --dump-config-schema
```

The composed dsh tree can configure the LLM provider and model, sessions, agents, authorization, credentials, UI, jobs, remote access, and other Cordis plugins. The `web` profile dump is the reference for the current installation. The profile is a runtime configuration tree, not a list of standalone skills.

The dsh adapter should therefore follow this ownership model:

```text
sm preset and tags
    ↓
resolve selected skills and optional runtime resources
    ↓
generate a temporary dsh patch
    ↓
dsh --profile BASE --patch TEMP_PATCH
```

Do not create a second profile database inside `sm-plugin`. Use dsh's profile and patch mechanisms. Persistent profile changes belong to dsh commands such as `dsh plugin --profile <name> ...`; per-conversation changes belong in a temporary `--patch` file.

A future dsh capability patch may disable or override a plugin by its profile entry ID, insert a selected plugin entry, change the model, or configure a session-specific tool source. The adapter must validate patch targets against `dsh --dump-config` before launch and retain the composed config for diagnostics when a launch fails.

The dsh profile does not automatically use Claude plugins, Codex skill roots, or Pi extensions. Those are different package formats. A shared capability profile needs a dsh-specific renderer and a dsh-specific verification step.
