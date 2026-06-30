---
name: connect-known-worker
description: "Resolve and connect to named local or remote CAO worker targets from a private .cao/known-workers.local.toml file. Use when the user says to connect to, open, resume, monitor, close, or attach to a named target, including Japanese requests ending in 繋げて, 開いて, 監視して, or クローズして, and the target is not already clearly handled by the current CAO list."
---

# Connect Known Worker

## Core Rule

Resolve named workers from `.cao/known-workers.local.toml` before improvising. This file is local-only and must not be committed. Keep target-specific hostnames, directories, account names, tmux session names, and runner choices out of tracked files.

## Local File

Look for `.cao/known-workers.local.toml` in the CAO repo root. Treat it as TOML.

Expected shape:

```toml
[workers.example]
kind = "local_codex"        # local_codex | local_claude | ssh_claude | ssh_codex | ssh_shell
runner = "codex"            # codex | claude | shell
name = "example"
directory = "/path/to/work"
resume = true

[workers.remote-example]
kind = "ssh_claude"
runner = "claude"
name = "remote-example"
ssh_alias = "RemoteHostAlias"
remote_dir = "~/work/repo"
remote_tmux_session = "remote-example"
command = "claude"

[workers.example.policy]
scope = "current work only"
external_writes = "Do not write to shared external systems without explicit approval."
allowed_without_approval = "Local implementation, local validation, and CAO-facing reports."
do_not_generalize = true
```

Never put credentials, OAuth codes, tokens, cookies, private keys, or one-time approval codes in this file.

## Target Policy

Entries may include an optional `policy` table for target-specific operating constraints. Treat these constraints as local instructions for that target only.

- Read and apply `policy` before sending work instructions, resuming, or reconnecting the target.
- Translate policy values into concise Worker-facing constraints; do not forward TOML or supervisor-only wording verbatim.
- If `do_not_generalize = true`, do not apply that policy to other Workers or future unrelated work.
- Keep target-specific policies in `.cao/known-workers.local.toml`, not tracked files.

## Resolve

1. Run `./bin/cao list` first. If the target is already tracked, capture it and continue there.
2. If not tracked, inspect `.cao/known-workers.local.toml` using the bundled resolver:

   ```bash
   python3 .codex/skills/connect-known-worker/scripts/known_worker.py get <name>
   ```

3. If the target is missing, ask for the minimum connection details needed and offer to store them in `.cao/known-workers.local.toml`.
4. If multiple entries could match, capture/list candidates and ask the user to choose.

## Connect

For local Codex or Claude workers:

```bash
./bin/cao add <directory> --runner <runner> --name <name> [--resume]
./bin/cao capture <name>
```

For SSH-backed Claude or Codex workers:

1. Create or reuse a CAO tmux window named after the worker.
2. Launch SSH and attach to a remote tmux session in the configured directory:

   ```bash
   tmux new-window -d -t CAO -n <name> \
     "ssh -tt <ssh_alias> 'cd <remote_dir> && tmux new-session -A -s <remote_tmux_session> -c <remote_dir> <command>'"
   ```

3. Register the CAO target with the configured runner:

   ```bash
   ./bin/cao register <name> --runner <runner>
   ```

4. Verify with `./bin/cao list` and `./bin/cao capture <name>`.

For shell-only SSH targets, use the same pattern with `runner` omitted or unknown, then verify with `tmux capture-pane`.

## Close

When the user says to close a known worker:

1. Capture the target once to confirm it is idle or safely closable.
2. If it is SSH-backed and has a `remote_tmux_session`, stop that remote session only when the user requested closure of the worker, not merely detaching.
3. Run `./bin/cao unregister <name>` if registered.
4. Kill the local CAO tmux window for that target.
5. Verify with `./bin/cao list`.

## Safety

- Do not edit user-level Codex config for this workflow.
- Do not commit `.cao/known-workers.local.toml`.
- Do not log or print secrets. The mapping file should contain only connection metadata.
- If the requested target maps to a public repository, also apply `public-repo-hygiene` before writing tracked files.
