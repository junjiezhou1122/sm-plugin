---
name: sm-plugin
description: "Use sm-plugin to inspect or combine Skills Manager presets and tags, prepare skills for Claude Code or Codex, launch a selected agent session, or save a selection as a new preset. Use when users ask to load preset or tagged skills together, preview a bundle, or reuse a skill combination."
---

# sm-plugin

Turn the user's requested presets and tags into an additive skill selection. Inspect the available choices, resolve exact selectors, then prepare, launch or save that selection through the CLI.

## 1. Check the tools

This skill requires the separately installed `sm-plugin` CLI, the official Skills Manager CLI bridge, and the agent used for launch. Run:

```sh
sm-plugin --help
sm-plugin doctor
```

If `sm-plugin` is missing, follow the [repository's CLI installation instructions](https://github.com/junjiezhou1122/sm-plugin#install). Installing this skill alone does not install the CLI. If the official bridge is incomplete, open Skills Manager to republish it, then rerun `doctor`. For a custom bridge, use its executable path with `sm-plugin --cli "$SM_CLI" doctor`.

Put global options `--cli` and `--root` before the subcommand. Choose a writable bundle root outside Skills Manager and global agent directories when the default root is unsuitable.

## 2. Resolve the selection

List presets with `sm-plugin presets`. For tags or membership, use the official bridge reported by `doctor`. This POSIX shell example uses the default published bridge; replace `SM_CLI` with the reported path when different:

```sh
SM_CLI="$HOME/.skills-manager/bin/skills-manager-cli"
"$SM_CLI" --json skills tag list
"$SM_CLI" --json skills list --tag "research"
"$SM_CLI" --json skills list --preset "PRESET_ID"
```

Use returned names and IDs, rather than guessing selectors. Ask only when the available choices leave a material ambiguity in the user's request.

Selection rules:

- Presets match an exact name or ID. Use an ID if a name is ambiguous, and quote names containing spaces.
- Repeat `--tag` for multiple tags. Tags match exactly, including case. Unknown tags fail.
- Presets and tags form a union. Tags alone are valid. Supply at least one preset or tag.
- Tag selection excludes skills carrying the exact `archived` tag. Explicit preset membership can still include them. Selecting `--tag archived` contributes no skills.
- Shared canonical skill paths appear once. Selector order and repetition do not change the selection. Distinct paths with the same case-insensitive folder name fail with a collision error. Inspect the reported paths and resolve the selection through Skills Manager.

## 3. Perform the requested action

Proceed with authorized inspection, local bundle generation and saving a new preset without repeated approval prompts. Launch an interactive agent only when the user requested that session. Interactive use can incur the agent's normal provider costs. Keep global deployment changes and additional paid provider calls within explicit user requests.

The names and tags below are examples. Substitute the exact selectors discovered above.

### Prepare or preview

```sh
sm-plugin sync "Frontend" "Research" --tag "writing"
sm-plugin --root "$HOME/sm-plugin-bundles" sync --tag "research" --tag "writing"
sm-plugin launch claude "Frontend" --tag "writing" --cwd "/path/to/project" --dry-run
```

`sync` prints the generated bundle path. `launch --dry-run` generates the local bundle and prints the resolved launch details without starting the agent. It is not a read-only preview. Neither action changes official presets or deployments.

Loading is additive. Global skills, project skills and installed plugins remain available. Exclusive isolation is unsupported. Bundles keep a membership snapshot, but their symlinks reflect later edits to source skill contents.

### Launch

```sh
sm-plugin launch claude "Frontend" --tag "writing" --cwd "/path/to/project"
sm-plugin launch claude "Frontend" --cwd "/path/to/project" -- --model opus
sm-plugin launch codex "Research" --tag "writing" --cwd "/path/to/project"
```

Forward Claude arguments after `--`. Keep the launched session attached; Claude background launch is unsupported. Codex accepts no forwarded arguments. Configure its model and permissions through native settings or its TUI.

Claude loads the generated plugin with `--plugin-dir`. Codex uses a private app-server and its native TUI. Both preserve native authentication and configuration.

### Save a reusable preset

Preview the new preset before saving:

```sh
sm-plugin save "Research + Writing" "Research" --tag "writing" --dry-run
sm-plugin save "Research + Writing" "Research" --tag "writing" --description "Research and writing skills"
sm-plugin presets
```

`save --dry-run` is read-only and lists resolved skill IDs and names. `save` creates a new official preset through the official CLI. It refuses an existing destination name and an empty selection. It saves a membership snapshot, so later tag changes do not update the preset. Saving does not deploy skills or change the active preset.

If creation succeeds but membership completion fails, inspect the new preset by its returned ID through the official bridge before retrying. Report the partial result instead of treating the save as complete or creating another preset blindly.

## 4. Verify and report

Check the result for the action performed. For a saved preset, inspect its membership with the official `skills list --preset` command. When agent compatibility needs checking, use:

```sh
sm-plugin verify claude "Frontend"
sm-plugin verify codex "Research" --tag "writing" --cwd "/path/to/project"
```

Verification generates a bundle but sends no model turns. Claude verification checks plugin structure; it does not prove a model invoked a skill. Codex verification checks enabled skill discovery through its experimental app-server API. Rerun `doctor` after official tool updates.

Report the resolved presets and tags, skill count, bundle path or saved preset ID, and any unresolved error. Distinguish a prepared command, a launched session and verified discovery.
