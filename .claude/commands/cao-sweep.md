---
description: Run one supervision sweep across all CAO worker windows.
allowed-tools: Bash(./bin/cao:*), Task
---

Delegate the actual capture-and-classify loop to the `cao-supervisor` subagent. It will:

1. enumerate CAO windows and registered external windows with `./bin/cao list`,
2. capture each non-`pm` target,
3. classify each worker as **working / waiting / blocked / asking / finished**,
4. return a compact triage table.

After the subagent reports back, **you decide and act**:

- Local, reversible, on-intent next step → `./bin/cao send <name> '<reply>'` directly.
- Drift from user intent → `./bin/cao send <name> '<correction>'`.
- High-impact, ambiguous, or outside escalation policy → surface to the user as a binary Yes/No question.

End by giving the user a one-line summary: how many workers in each state, what you sent, and what (if anything) needs their decision.
