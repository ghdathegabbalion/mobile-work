# Reciprocal Dawn Protocol — spec

**Status: stub.** Nothing here is designed yet. This file exists so the idea
has somewhere to become real, and so the questions below stop being answerable
by adding another bullet point.

## What exists so far

One line, from a generated architecture document:

> Advisory governance kernel, risk bands, constraint precedence, dilemma
> predicate.

That is a name and four nouns. It is more specific than most of the document it
came from — it describes a decision procedure rather than a capability list —
but it is not yet a design.

## Questions the spec has to answer

Answering any one of these in concrete terms is worth more than expanding the
outline. Roughly in dependency order:

### 1. What is being governed, and by what?

- What produces the actions RDP evaluates?
- What does RDP receive — an action, a plan, a proposed state change?
- What does it emit?

### 2. "Advisory" — advising whom?

The word implies RDP does **not** enforce. So:

- Who consumes the advice?
- What happens when the advice is ignored? If nothing, RDP is logging. If
  something, it is enforcing and the word is wrong.
- Is being overridable a deliberate design position, or an unfinished part?

### 3. Risk bands

- How many, and what distinguishes them?
- What assigns an action to a band — a classifier, a rule set, a human?
- Is band assignment auditable after the fact?

### 4. Constraint precedence

- Is the ordering total or partial?
- Who sets it, and can it change at runtime?
- If it can change, what stops the system from reordering its way out of a
  constraint it dislikes?

### 5. The dilemma predicate

The most interesting piece, and the one most likely to be load-bearing.

- What exactly does it test for? Presumably: two constraints that cannot both
  be satisfied and whose precedence does not resolve the conflict.
- **What happens when it fires?** Halt, escalate to a human, log and proceed,
  pick arbitrarily and record that it was arbitrary — these are four different
  systems.
- Can it be wrong in both directions — miss a real dilemma, or fire on a
  conflict that precedence actually did resolve?

### 6. Smallest real version

What is the least amount of this that can be built and run against a handful of
example cases? That artifact settles more than the rest of the outline will.

## Notes

- Owner: Vesper (Codex), with the human. Claude is reviewing, not designing.
- Claimed as advisory yet listed alongside a fail-closed hardware veto in the
  source document. Those are not peers; if RDP is genuinely advisory, that
  document misrepresents it.
