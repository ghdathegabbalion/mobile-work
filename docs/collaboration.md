# Two agents, one repo

Claude Code and Codex (Vesper) both work in `mobile-work`. There is no live
channel between them: no shared memory, no messaging, no way for one to read
the other's session. **Git is the only bus.** Everything below exists to make
that constraint workable instead of annoying.

Each agent reads its own instructions file — `CLAUDE.md` and `AGENTS.md` — and
both point here for the shared rules.

## Lanes

| Agent | Branch prefix |
|---|---|
| Claude Code | `claude/*` |
| Codex (Vesper) | `vesper/*` |

One agent per branch, always. Merge to `main` through pull requests. Two agents
on one branch produces conflicts that neither can see coming, because neither
knows the other is working.

## The review loop

This is the pattern worth using, and the only one that produces something
neither agent manages alone.

1. Author works in its lane and opens a **draft PR**.
2. The other agent reviews it on its next session — read the diff, argue with
   it, leave comments or push fixes to the same branch **only if the author is
   done with it**.
3. The human arbitrates.

The value is that the two models have different blind spots. The failure mode
is that they also have overlapping ones, and two confident agents can agree
enthusiastically on something wrong. Model review catches real errors; it is
not a substitute for the human deciding.

## Handoff notes

For work that crosses sessions but isn't ready to be a PR — a half-finished
design, an open question, a decision that needs to survive a dead context
window — write a note in `docs/handoffs/`.

- Copy [`TEMPLATE.md`](handoffs/TEMPLATE.md).
- Name it `YYYY-MM-DD-short-slug.md`.
- Delete notes once the work lands. Stale handoffs are worse than none, because
  the next agent cannot tell they are stale.

## The one rule that matters

**Write for a reader with zero context.** The other agent has not seen your
session and never will. Neither will you, next week. Every handoff, PR
description, and note has to carry its own context or it is useless.
