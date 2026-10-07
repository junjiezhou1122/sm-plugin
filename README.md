# sm-plugin

Generate real skill folders from Skills Manager presets and launch Claude Code or Codex with the selected preset.

**Loading is additive.** Global skills, project skills and installed plugins remain available. This version does not provide exclusive skill isolation. `--mode exclusive` exits with an error.

## Install

Requires Python 3.11+, an installed Skills Manager CLI, and Claude Code or Codex. Codex integration uses a Unix socket and has been verified on macOS. Other operating systems have not been verified.

```sh
git clone https://github.com/junjiezhou1122/sm-plugin.git
cd sm-plugin
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/sm-plugin doctor
```

Use `.venv/bin/sm-plugin` or add the virtual environment's bin directory to your PATH. The commands below assume `sm-plugin` is on PATH.

## Use

```sh
sm-plugin presets
sm-plugin sync "Frontend"
sm-plugin launch claude "Frontend" --dry-run
sm-plugin launch claude "Frontend"
sm-plugin launch codex "Research"
sm-plugin doctor
```

Create presets and manage their membership in Skills Manager. Select a preset by exact name or ID. Empty presets add no skills. Launch automatically generates the selected bundle.

Pass Claude options after `--`.

```sh
sm-plugin launch claude "Frontend" --cwd /path/to/project -- --model opus
```

Codex launch currently rejects forwarded arguments. Configure model and permissions through native settings or the TUI. Claude detached background launch is also refused.

## Generated folders

The default output is `bundles/` beside the installed Python module. To choose a persistent writable location, pass `--root` before the subcommand.

```sh
sm-plugin --root ~/sm-plugin-bundles sync "Frontend"
```

Each bundle contains a `skills/` directory with symlinks to the central library, a Claude plugin manifest, and a membership manifest. Folder names use a hashed preset ID and a membership fingerprint. Repeated sync returns the same folder. Changing membership generates a new folder, leaving previous bundles available to running sessions.

Bundles freeze membership, not skill contents. Updates to library contents remain visible through symlinks. Removing a source skill can leave a broken link. Existing bundles are never automatically deleted. Modified bundles and unmanaged output roots are refused.

## Agent integration

Claude loads a bundle with `--plugin-dir`. Skill commands use the generated plugin namespace, such as `/sm-<hash>:skill-name`.

Codex starts a private app-server for each launch, registers `skills/extraRoots/set`, then connects its native TUI with `--remote unix://<socket>`. The server stops when the TUI exits. Each server has independent extra skill roots. Native account configuration and session storage remain shared.

The tool preserves native authentication and configuration. It does not copy credentials or change global skill directories.

## Official updates

sm-plugin is an independent integration with Skills Manager. It reads `presets list` and `skills list --preset` through the official CLI with `--json`. It does not modify the official app, database, library contents or deployments.

Run `doctor` after official updates to check the CLI bridge and launch flags. Use `verify codex <preset>` to exercise the experimental app-server API. These checks detect some compatibility changes; they do not guarantee compatibility with future releases.

Verified versions are Skills Manager CLI 1.40.3, Claude Code 2.1.292, Codex 0.160.1 and websockets 16.0. Codex's app-server API is experimental.

## Verification

```sh
sm-plugin verify claude "Frontend"
sm-plugin verify codex "Research"
python3 -m unittest discover -s . -v
python3 verify_runtime.py
```

The test suite covers idempotent generation, concurrent first generation, retained membership snapshots, malformed records, path traversal and protection of unmanaged files.

Claude verification uses the official plugin validator. It checks package structure and reports that skill symlinks are not followed during validation. Its diagnostic states that runtime loading follows them. This does not prove a model has invoked a skill.

Codex verification registers the preset roots, reconnects and checks actual enabled skills through `skills/list`. `verify_runtime.py` uses one temporary skill to verify nonempty discovery. Verification sends no model turns. Normal interactive use can incur the agent's usual provider costs.
