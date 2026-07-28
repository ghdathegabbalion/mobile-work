"""Executable reference for the Reciprocal Dawn Protocol dilemma predicate."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Iterable, Mapping, Sequence


Facts = Mapping[str, object]
Predicate = Callable[[Facts], bool]


@dataclass(frozen=True)
class Candidate:
    id: str
    facts: Facts


@dataclass(frozen=True)
class Constraint:
    id: str
    description: str
    predicate: Predicate


@dataclass(frozen=True)
class Conflict:
    constraints: tuple[str, ...]
    maximal: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    outcome: str
    policy_version: str
    recommended: tuple[str, ...]
    conflicts: tuple[Conflict, ...]
    evaluations: Mapping[str, Mapping[str, bool]]
    precedence: tuple[tuple[str, str], ...]
    reason: str


def evaluate(
    candidates: Sequence[Candidate],
    constraints: Sequence[Constraint],
    precedence: Iterable[tuple[str, str]],
    *,
    policy_version: str,
) -> Decision:
    """Evaluate one finite proposal without executing a candidate."""
    if not candidates:
        raise ValueError("at least one candidate is required")
    if not constraints:
        raise ValueError("at least one constraint is required")

    constraint_ids = tuple(constraint.id for constraint in constraints)
    if len(set(constraint_ids)) != len(constraint_ids):
        raise ValueError("constraint IDs must be unique")
    if len({candidate.id for candidate in candidates}) != len(candidates):
        raise ValueError("candidate IDs must be unique")

    edges = tuple(precedence)
    reachability = _transitive_closure(constraint_ids, edges)
    evaluations = {
        candidate.id: {
            constraint.id: bool(constraint.predicate(candidate.facts))
            for constraint in constraints
        }
        for candidate in candidates
    }

    fully_satisfying = tuple(
        candidate.id
        for candidate in candidates
        if all(evaluations[candidate.id].values())
    )
    if fully_satisfying:
        return Decision(
            outcome="approve",
            policy_version=policy_version,
            recommended=fully_satisfying,
            conflicts=(),
            evaluations=evaluations,
            precedence=edges,
            reason="At least one candidate satisfies every applicable constraint.",
        )

    impossible = tuple(
        constraint_id
        for constraint_id in constraint_ids
        if not any(
            evaluations[candidate.id][constraint_id] for candidate in candidates
        )
    )
    if impossible:
        return Decision(
            outcome="infeasible",
            policy_version=policy_version,
            recommended=(),
            conflicts=(
                Conflict(constraints=impossible, maximal=_maximal(impossible, reachability)),
            ),
            evaluations=evaluations,
            precedence=edges,
            reason=(
                "The proposal contains no candidate satisfying: "
                + ", ".join(impossible)
                + ". Add candidates or explicitly change policy."
            ),
        )

    conflict_sets = _minimal_conflict_sets(
        constraint_ids, candidates, evaluations
    )
    conflicts = tuple(
        Conflict(
            constraints=conflict_set,
            maximal=_maximal(conflict_set, reachability),
        )
        for conflict_set in conflict_sets
    )
    unresolved = tuple(
        conflict for conflict in conflicts if len(conflict.maximal) > 1
    )
    if unresolved:
        return Decision(
            outcome="dilemma",
            policy_version=policy_version,
            recommended=(),
            conflicts=unresolved,
            evaluations=evaluations,
            precedence=edges,
            reason=(
                "Minimal conflict sets contain incomparable maximal constraints; "
                "precedence cannot authorize a recommendation."
            ),
        )

    local_winners = {
        conflict.maximal[0]
        for conflict in conflicts
        if len(conflict.maximal) == 1
    }
    required = tuple(
        item
        for item in constraint_ids
        if item in local_winners
    )
    recommended = tuple(
        candidate.id
        for candidate in candidates
        if all(evaluations[candidate.id][constraint_id] for constraint_id in required)
    )
    if not recommended:
        second_order_maximal = _maximal(required, reachability)
        if len(second_order_maximal) > 1:
            return Decision(
                outcome="dilemma",
                policy_version=policy_version,
                recommended=(),
                conflicts=conflicts
                + (Conflict(constraints=required, maximal=second_order_maximal),),
                evaluations=evaluations,
                precedence=edges,
                reason=(
                    "Local precedence winners cannot coexist and remain "
                    "incomparable; no recommendation is authorized."
                ),
            )
        recommended = tuple(
            candidate.id
            for candidate in candidates
            if evaluations[candidate.id][second_order_maximal[0]]
        )
    return Decision(
        outcome="resolved",
        policy_version=policy_version,
        recommended=recommended,
        conflicts=conflicts,
        evaluations=evaluations,
        precedence=edges,
        reason=(
            "Each minimal conflict set has one unique maximal constraint; "
            "recommendations satisfy every such constraint."
        ),
    )


def _minimal_conflict_sets(
    constraint_ids: Sequence[str],
    candidates: Sequence[Candidate],
    evaluations: Mapping[str, Mapping[str, bool]],
) -> tuple[tuple[str, ...], ...]:
    found: list[tuple[str, ...]] = []
    for size in range(2, len(constraint_ids) + 1):
        for subset in combinations(constraint_ids, size):
            if any(
                all(evaluations[candidate.id][item] for item in subset)
                for candidate in candidates
            ):
                continue
            if not any(set(existing).issubset(subset) for existing in found):
                found.append(subset)
    if not found:
        raise RuntimeError("no conflict set found for a proposal with no valid candidate")
    return tuple(found)


def _transitive_closure(
    constraint_ids: Sequence[str],
    edges: Sequence[tuple[str, str]],
) -> set[tuple[str, str]]:
    known = set(constraint_ids)
    closure = set(edges)
    for higher, lower in closure:
        if higher not in known or lower not in known:
            raise ValueError("precedence edges must name known constraints")
        if higher == lower:
            raise ValueError("precedence cannot contain self-edges")

    changed = True
    while changed:
        changed = False
        additions = {
            (start, end)
            for start, middle in closure
            for candidate_middle, end in closure
            if middle == candidate_middle and (start, end) not in closure
        }
        if additions:
            closure.update(additions)
            changed = True
    if any((item, item) in closure for item in known):
        raise ValueError("precedence must be acyclic")
    return closure


def _maximal(
    constraint_ids: Sequence[str],
    reachability: set[tuple[str, str]],
) -> tuple[str, ...]:
    return tuple(
        item
        for item in constraint_ids
        if not any(
            other != item and (other, item) in reachability
            for other in constraint_ids
        )
    )
