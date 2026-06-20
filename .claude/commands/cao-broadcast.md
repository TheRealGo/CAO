---
description: Broadcast the same message to every CAO worker window. Use sparingly.
argument-hint: <MESSAGE>
allowed-tools: Bash(./bin/cao:*)
---

Message: `$ARGUMENTS`

Broadcasting interrupts every worker, including ones in the middle of unrelated tasks. Unless the message is clearly benign (e.g. `please summarize current progress`, `please save your work and stop`), **confirm with the user first** before sending.

Steps:

1. Run `./bin/cao list` to enumerate windows.
2. For each window whose name is **not** `pm`, run `./bin/cao send <name> '$ARGUMENTS'`.
3. Wait 1-2 seconds, then `./bin/cao capture <name> --lines 20` for each window to confirm receipt.
4. Report which workers acknowledged and which did not respond.
