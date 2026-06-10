---
description: Deep-dive one stuck CAO worker and propose a recovery instruction.
argument-hint: <TARGET>
allowed-tools: Bash(./bin/cao:*), Bash(tmux capture-pane:*), Bash(tmux display-message:*), Task, Read, Grep
---

Target window: `$1`

Delegate the diagnosis to the `cao-rescue` subagent. It will read deep pane history (and the working tree if needed) and return:

- root cause (one sentence),
- proposed instruction text,
- confidence,
- escalation flag.

After the subagent reports:

1. Show the proposed instruction to the user, then either:
   - Send it now with `./bin/cao send $1 '<instruction>'` if confidence is high and it is on-intent and reversible, **or**
   - Ask the user to confirm or amend if the escalation flag is true or confidence is medium/low.
2. After sending, capture `$1` and confirm the worker accepted the input and moved.
