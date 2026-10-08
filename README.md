# sm-plugin

Generate real skill folders from Skills Manager presets and tags, launch Claude Code or Codex with the selection, or save its membership as a new preset.

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

## AI skill

Install the portable [sm-plugin skill](skills/sm-plugin/SKILL.md) so your AI agent can discover presets and tags, combine selections, prepare or launch a session, and save a reusable preset:

```sh
npx skills add junjiezhou1122/sm-plugin --skill sm-plugin
```

The skill is in `skills/sm-plugin/` and can also be imported through Skills Manager using its Git tree URL:

```text
https://github.com/junjiezhou1122/sm-plugin/tree/main/skills/sm-plugin
```

Installing the skill adds agent instructions. Install the `sm-plugin` CLI separately using the steps above, then run `sm-plugin doctor`. Try asking your agent to "combine my Research preset with the writing tag and save it as Research + Writing" or "preview a Claude session with my Frontend preset."

## Use

```sh
sm-plugin presets
sm-plugin sync "Frontend"
sm-plugin launch claude "Frontend" --dry-run
sm-plugin launch claude "Frontend"
sm-plugin launch codex "Research"
sm-plugin sync nature deli
sm-plugin launch claude nature deli --dry-run
sm-plugin launch claude nature deli
sm-plugin verify codex nature deli
sm-plugin verify codex --tag deli
sm-plugin launch codex nature --tag deli
sm-plugin sync --tag nature --tag deli
sm-plugin save "Nature + Deli" nature --tag deli --dry-run
sm-plugin save "Nature + Deli" nature --tag deli --description "Research and paper writing"
sm-plugin doctor
```

Create presets and manage their membership in Skills Manager. Select presets by exact name or ID, separated by spaces. Quote names that contain spaces. Empty presets add no skills. Launch automatically generates the selected bundle.

Multiple presets compose into the union of their canonical skill paths. Shared skills appear once. Distinct paths with the same case-insensitive skill folder name cause an error that lists both paths. Selection order and repeated selectors do not change the composed bundle. Single-preset commands keep their existing bundle paths.

Add repeatable `--tag TAG` selectors to `sync`, `launch`, `verify` or `save`. Presets and tags select a union; tags alone are allowed. Tags match exactly, including case, and unknown tags cause an error. Tag selection excludes skills carrying the exact `archived` tag. Explicit preset membership still includes archived skills. Selecting `--tag archived` therefore contributes no skills. Commands require at least one preset or tag. Launch dry-run output lists the contributing presets, tags and skill count.

`save NAME [PRESET ...] [--tag TAG ...]` creates a new official Skills Manager preset with the selected source skill IDs. It validates skill paths, name collisions and current IDs before creation, refuses an existing destination name, and rejects empty selections. `--description` adds an optional description. `--dry-run` is read-only and prints the resolved skill IDs and names without generating a bundle. The saved preset is a membership snapshot; later tag changes do not change it. Saving changes preset membership only and does not deploy skills or change the active preset. If creation succeeds but adding membership fails, inspect the new preset in Skills Manager before retrying.

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

Each bundle contains a `skills/` directory with symlinks to the central library, a Claude plugin manifest, and a membership manifest. Folder names use a hashed preset ID, or sorted preset IDs and tags for a composition, and a membership fingerprint. Composed manifests also record the contributing preset IDs, names and tags. Repeated sync returns the same folder. Changing membership generates a new folder, leaving previous bundles available to running sessions.

Bundles freeze membership, not skill contents. Updates to library contents remain visible through symlinks. Removing a source skill can leave a broken link. Existing bundles are never automatically deleted. Modified bundles and unmanaged output roots are refused.

## Agent integration

Claude loads a bundle with `--plugin-dir`. Skill commands use the generated plugin namespace, such as `/sm-<hash>:skill-name`.

Codex starts a private app-server for each launch, registers `skills/extraRoots/set`, then connects its native TUI with `--remote unix://<socket>`. The server stops when the TUI exits. Each server has independent extra skill roots. Native account configuration and session storage remain shared.

The tool preserves native authentication and configuration. It does not copy credentials or change global skill directories.

## Official updates

sm-plugin is an independent integration with Skills Manager. It reads presets, skills and tags through the official CLI with `--json`. Only `save` writes to Skills Manager, using official `presets create` and `presets add-skill` commands. It never edits the database directly or modifies the official app, library contents or deployments.

Run `doctor` after official updates to check the CLI bridge and launch flags. Use `verify codex <preset>` to exercise the experimental app-server API. These checks detect some compatibility changes; they do not guarantee compatibility with future releases.

Verified versions are Skills Manager CLI 1.40.3, Claude Code 2.1.292, Codex 0.160.1 and websockets 16.0. Codex's app-server API is experimental.

## Verification

```sh
sm-plugin verify claude "Frontend"
sm-plugin verify codex "Research"
python3 -m unittest discover -s . -v
python3 verify_runtime.py
```

The test suite covers composition order, shared-path and ID deduplication, exact tags, archived filtering, unknown tags, missing selectors, name collisions, single-preset compatibility, snapshot saving by ID, read-only save previews, existing-name refusal, argument forwarding, idempotent generation, concurrent first generation, retained membership snapshots, malformed records, path traversal and protection of unmanaged files.

Claude verification uses the official plugin validator. It checks package structure and reports that skill symlinks are not followed during validation. Its diagnostic states that runtime loading follows them. This does not prove a model has invoked a skill.

Codex verification registers the preset roots, reconnects and checks actual enabled skills through `skills/list`. `verify_runtime.py` uses one temporary skill to verify nonempty discovery. Verification sends no model turns. Normal interactive use can incur the agent's usual provider costs.
