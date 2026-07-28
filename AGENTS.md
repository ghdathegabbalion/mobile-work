# AGENTS.md — for Codex (Vesper)

Read this first. It is your counterpart to `CLAUDE.md`, which is Claude Code's
instructions file for this repo. Two agents work here. Neither can see the
other's session, memory, or context — the repo is the only thing you share.

## What this repo is

`mobile-work` is a workspace for driving work from a phone. It holds code,
docs, notes, character/design sheets, and small tools. It deliberately stays
minimal and grows as needed.

Do not add model weights, large media, or secrets. The heavy art workspace
lives on the owner's PC at `C:\Users\GH-DA\ComfyUI-Shared` and is referenced,
never copied in.

## Where you are

You run in a cloud sandbox: **text only**. No GPU, no ComfyUI, no access to the
PC's filesystem. Edit code, docs, notes, and workflow JSON. Do not attempt to
render anything or assume `ComfyUI-Shared` is reachable.

## Your lane

- Branch prefix: **`vesper/*`** (e.g. `vesper/rdp-spec`).
- Claude Code uses **`claude/*`**.
- **Never commit to a branch carrying the other prefix**, and never both work a
  single branch. That is the whole conflict-avoidance scheme.
- Merge to `main` through pull requests.

## Working conventions

- **Be concise.** Output is read on a phone. Lead with the answer.
- **Commit and push often.** This repo syncs across phone, cloud, and PC.
  Small frequent commits keep the three aligned.
- `git pull` at the start of a session — the other agent may have moved things.

## Handing off

See [docs/collaboration.md](docs/collaboration.md) for the full protocol. The
short version:

1. **Assume the other agent knows nothing.** It has no memory of your session
   and never will. A handoff that depends on unstated context is dead on
   arrival.
2. For work that ends in code or docs: open a **draft PR** and let the other
   agent review it.
3. For work that crosses sessions without a PR: write a handoff note in
   `docs/handoffs/` using [the template](docs/handoffs/TEMPLATE.md).
4. Disagreements go to the human. Two models agreeing is not evidence.
