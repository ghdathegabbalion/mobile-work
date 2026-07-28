import unittest

from docs.rdp.reference import Candidate, Constraint, evaluate


def has(name):
    return lambda facts: bool(facts.get(name))


class DilemmaPredicateTests(unittest.TestCase):
    def test_approves_candidate_satisfying_every_constraint(self):
        decision = evaluate(
            [Candidate("safe", {"consent": True, "helpful": True})],
            [
                Constraint("consent", "User consent is present", has("consent")),
                Constraint("helpful", "Action advances the request", has("helpful")),
            ],
            [],
            policy_version="test-1",
        )
        self.assertEqual("approve", decision.outcome)
        self.assertEqual(("safe",), decision.recommended)

    def test_precedence_resolves_conflict(self):
        decision = evaluate(
            [
                Candidate("ask", {"consent": True, "speed": False}),
                Candidate("act", {"consent": False, "speed": True}),
            ],
            [
                Constraint("consent", "Obtain consent", has("consent")),
                Constraint("speed", "Act immediately", has("speed")),
            ],
            [("consent", "speed")],
            policy_version="test-2",
        )
        self.assertEqual("resolved", decision.outcome)
        self.assertEqual(("ask",), decision.recommended)
        self.assertEqual(("consent",), decision.conflicts[0].maximal)

    def test_incomparable_constraints_create_dilemma(self):
        decision = evaluate(
            [
                Candidate("disclose", {"transparency": True, "privacy": False}),
                Candidate("withhold", {"transparency": False, "privacy": True}),
            ],
            [
                Constraint("transparency", "Disclose the reason", has("transparency")),
                Constraint("privacy", "Do not expose private data", has("privacy")),
            ],
            [],
            policy_version="test-3",
        )
        self.assertEqual("dilemma", decision.outcome)
        self.assertEqual((), decision.recommended)
        self.assertEqual(
            ("transparency", "privacy"), decision.conflicts[0].maximal
        )

    def test_impossible_constraint_is_infeasible_not_dilemma(self):
        decision = evaluate(
            [
                Candidate("one", {"safe": False}),
                Candidate("two", {"safe": False}),
            ],
            [Constraint("safe", "Must be safe", has("safe"))],
            [],
            policy_version="test-4",
        )
        self.assertEqual("infeasible", decision.outcome)
        self.assertEqual((), decision.recommended)

    def test_incompatible_local_winners_create_second_order_dilemma(self):
        decision = evaluate(
            [
                Candidate("left", {"a": True, "b": False, "c": False}),
                Candidate("middle", {"a": False, "b": True, "c": False}),
                Candidate("right", {"a": False, "b": False, "c": True}),
            ],
            [
                Constraint("a", "A", has("a")),
                Constraint("b", "B", has("b")),
                Constraint("c", "C", has("c")),
            ],
            [("a", "b"), ("c", "b")],
            policy_version="test-5",
        )
        self.assertEqual("dilemma", decision.outcome)
        self.assertEqual((), decision.recommended)
        self.assertEqual(("a", "c"), decision.conflicts[-1].maximal)

    def test_rejects_cyclic_precedence(self):
        with self.assertRaisesRegex(ValueError, "acyclic"):
            evaluate(
                [
                    Candidate("left", {"a": True, "b": False}),
                    Candidate("right", {"a": False, "b": True}),
                ],
                [
                    Constraint("a", "A", has("a")),
                    Constraint("b", "B", has("b")),
                ],
                [("a", "b"), ("b", "a")],
                policy_version="test-6",
            )


if __name__ == "__main__":
    unittest.main()
