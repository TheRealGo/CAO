---
description: Spawn a CAO worker window on a directory and report its initial state.
argument-hint: <DIR> [--name NAME] [--runner claude|codex] [--prompt TEXT] [--resume]
allowed-tools: Bash(./bin/cao:*), Bash(tmux capture-pane:*), Bash(tmux list-windows:*), Bash(tmux show-options:*), Read, Grep
---

Start a worker window using `./bin/cao add` with the user's arguments, then verify it came up.

Arguments: $ARGUMENTS

Steps:

1. Run `./bin/cao add $ARGUMENTS`. The directory basename is used as the window name when `--name` is omitted.
2. Wait ~2 seconds, then run `./bin/cao capture <name> --lines 40` to see whether the runner started.
3. Triage in one short paragraph:
   - which runner is in use,
   - whether the worker is at a prompt or already processing,
   - what you sent (if anything),
   - what the user should expect next.
4. If the user's original request already implies a task, send it now with `./bin/cao send <name> '<task>'` and verify with another capture.

Do not invent additional flags. Pass `$ARGUMENTS` through verbatim.
