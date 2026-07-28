# Reciprocal Dawn Protocol — dilemma predicate

**Status: candidate v0.1.** This version defines one load-bearing part of RDP
and includes a runnable reference implementation. It deliberately does not
pretend the rest of the governance kernel is designed.

## Decision boundary

RDP evaluates a finite proposal: a set of candidate actions against a frozen
policy snapshot. The producer may be a planner, tool router, or human. RDP does
not execute an action.

The v0.1 input is:

- candidate actions, each with the facts used to evaluate it;
- applicable constraints, each expressed as a deterministic predicate;
- a directed, acyclic precedence graph where `A -> B` means A outranks B; and
- a policy version supplied by the caller.

The output is a decision record:

- `approve`: at least one candidate satisfies every applicable constraint;
- `resolved`: constraints conflict, but precedence identifies one unique
  highest constraint and at least one candidate satisfies it;
- `dilemma`: constraints conflict and precedence cannot choose among the
  highest constraints;
- `infeasible`: at least one constraint cannot be satisfied by any candidate;
  this is a bad or incomplete proposal, not a dilemma.

Every result includes the policy version and the pass/fail matrix for every
candidate and constraint. `resolved`, `dilemma`, and `infeasible` also include
the smallest conflict set that explains the result.

## The dilemma predicate

Let:

- `A` be the finite set of candidate actions;
- `C` be the applicable constraints;
- `satisfies(a, c)` mean candidate `a` satisfies constraint `c`; and
- `>` be the transitive, partial precedence relation over `C`.

A set `U`, where `U` is a subset of `C`, is a **minimal conflict set** when:

1. no candidate in `A` satisfies every constraint in `U`; and
2. every proper subset of `U` is jointly satisfiable by at least one candidate.

For a minimal conflict set `U`, let `max(U)` be its constraints that are not
outranked by another member of `U`.

The predicate is:

```text
dilemma(A, C, >) :=
    exists minimal conflict set U:
        every c in U is individually satisfiable
        and |max(U)| > 1
```

The `individually satisfiable` clause separates a genuine conflict from a
proposal that simply omitted every acceptable action. The `|max(U)| > 1`
clause means precedence did not resolve the conflict: two or more maximal
constraints remain incomparable.

This definition supports multiple independent conflict sets. RDP reports every
inclusion-minimal set rather than returning whichever one enumeration found
first.

## Required behavior

### When the predicate is false

- If a candidate satisfies all constraints, recommend one of those candidates.
- If a conflict has one unique maximal constraint, recommend only candidates
  that satisfy it. Record which lower constraints would be waived.
- If any constraint is individually unsatisfiable, return `infeasible` and no
  recommendation. The producer must add candidates, change the proposal, or
  explicitly change policy.

RDP v0.1 does not choose between multiple equally valid candidates. It returns
them in input order.

### When the predicate is true

Return `dilemma`, recommend no candidate, and escalate to the human authority.
The record must contain:

- every inclusion-minimal conflict set;
- the incomparable maximal constraints in each set;
- the complete candidate/constraint evaluation matrix;
- the precedence edges and policy version used; and
- the exact reason no recommendation was made.

The caller may ignore advisory output, but it must do so explicitly. An
integration claiming fail-closed behavior must refuse execution on `dilemma`
and `infeasible`; that enforcement belongs to the integration, not to RDP.

## Precedence integrity

Precedence is a partial order, not a mutable score. The v0.1 evaluator rejects:

- edges naming unknown constraints;
- self-edges; and
- cycles.

The policy version and precedence edges are copied into the decision record.
Changing precedence therefore creates a different auditable decision. Policy
authorization, signatures, and persistence remain outside this prototype.

## Known error modes

False negatives are possible when the producer omits a relevant constraint or
candidate, or a constraint predicate returns a false pass. False positives are
possible when a predicate returns a false failure or when the precedence graph
omits a legitimate edge.

The evaluator cannot cure either class of error. It makes them inspectable:
the caller can see the exact proposal, predicate results, precedence graph, and
policy version that produced the decision.

## Smallest real version

[`reference.py`](reference.py) implements the definition using only the Python
standard library. [`test_reference.py`](test_reference.py) covers:

1. a candidate satisfying all constraints;
2. a conflict resolved by precedence;
3. an unresolved two-constraint dilemma;
4. an individually impossible constraint; and
5. incompatible local precedence winners; and
6. rejection of cyclic precedence.

Run it from the repository root:

```powershell
python -m unittest docs.rdp.test_reference -v
```

The reference is executable specification, not production policy machinery.
It intentionally leaves classification, policy authorship, storage, human
identity, and enforcement for later designs.

## Open questions after v0.1

- Which component constructs the finite candidate set?
- Which constraints are allowed to be waived after a precedence resolution?
- How is policy authorship authorized and versioned?
- What risk bands, if any, decide whether an integration may proceed
  automatically?
- What schema persists decision records without allowing silent revision?

Owner: Vesper (Codex), with the human. Aster reviews; the human arbitrates.
