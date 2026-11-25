"""Independent small-horizon arithmetic and SQLite policy evaluation.

These checks do not use ExactPlanner.rollout, code_metrics, terminal_score, or
the finite step function when evaluating a saved policy's realized utility.
The planner still supplies its policy using only a message/public history.
"""
from fractions import Fraction as Q
import unittest

from etal.sequential import (
    Costs, ExactPlanner, NO_CODE, ONE_SYMBOL_CODES, SUFFICIENT_CODE,
    deployment_bytes, deployment_frames, make_row, normalize, pack_frame,
    partition, unpack_frame,
)
from etal.stateful import State, initial_worlds, observation_index, sender_observation
from etal.sqlite_backend import SQLiteBackend


SOURCE_CODE = ("a", "a", "b", "b")


def sqlite_policy_value(planner, code):
    """Enumerate initial worlds; independently score real SQLite trajectories.

    A transcript-to-action map checks that worlds with the same received
    message and public history cannot choose different actions.  Actual state
    is used only to initialize the environment and to score it after the job.
    """
    total = Q(0)
    actions_by_public_history = {}
    for initial, probability in initial_worlds(planner.branch):
        message = code[observation_index(sender_observation(initial))]
        belief = planner.initial_belief(code, message)
        history = ()
        finalized = False
        fees = Q(0)
        with SQLiteBackend(initial, planner.branch) as backend:
            for remaining in range(planner.max_calls, 0, -1):
                action = planner.choose(belief, remaining)
                key = (message, history)
                if key in actions_by_public_history:
                    if actions_by_public_history[key] != action:
                        raise AssertionError("hidden-state-dependent policy action")
                else:
                    actions_by_public_history[key] = action
                # Independent action-fee dispatch: do not call Costs.action.
                if action[:6] == "WRITE_":
                    fees += planner.costs.write
                elif action[:8] == "INSPECT_":
                    fees += planner.costs.inspect
                elif action[:7] == "REPAIR_":
                    fees += planner.costs.repair
                elif action != "FINALIZE":
                    raise AssertionError("unknown action")
                observation, finalized = backend.step(action)
                history += ((action, observation),)
                if finalized:
                    break
                belief, done = planner.update(belief, action, observation)
                if done:
                    raise AssertionError("non-finalized backend disagrees with policy")
            final = backend.snapshot()
            reward = Q(int(finalized and final.counts == (1, 1)))
            if final.damaged:
                reward -= planner.costs.damage
            total += probability * (reward - fees)
    return total


class TestSequentialOracle(unittest.TestCase):
    def test_two_call_values_derived_by_hand(self):
        planner = ExactPlanner("N", Costs(inspect=Q(1, 10)), max_calls=2)
        # Only one tool call can precede FINALIZE. For source-code A=0,
        # WRITE_A succeeds with probability 3/8: 3/8-1/50=71/200.
        # For A=1, idempotent WRITE_B succeeds with probability 7/8:
        # 7/8-1/50=171/200. Their equally weighted mean is 121/200.
        self.assertEqual(planner.code_value(SOURCE_CODE), Q(121, 200))
        # Full receipts: (0,0) cannot finish both writes; (0,1)/(1,0)
        # each achieve 3/4-1/50, and (1,1) finalizes immediately.
        self.assertEqual(planner.code_value(SUFFICIENT_CODE), Q(123, 200))
        # No message: WRITE_B succeeds with probability 7/16; subtract 1/50.
        self.assertEqual(planner.code_value(NO_CODE), Q(167, 400))

    def test_policy_value_matches_independent_sqlite_enumeration(self):
        # Every initial state/fault is enumerated, with exact rational weights.
        # Four calls permit observation-dependent recovery, not just a macro.
        for branch in ("N", "C", "F"):
            planner = ExactPlanner(branch, Costs(inspect=Q(1, 10)), max_calls=4)
            for code in (SOURCE_CODE, NO_CODE, SUFFICIENT_CODE):
                with self.subTest(branch=branch, code=code):
                    self.assertEqual(sqlite_policy_value(planner, code), planner.code_value(code))

    def test_paid_inspection_is_charged_once(self):
        belief = normalize(((State((0, 1)), Q(1, 2)), (State((1, 1)), Q(1, 2))))
        free = ExactPlanner("N", Costs(inspect=Q(0)), max_calls=3)
        paid = ExactPlanner("N", Costs(inspect=Q(1, 10)), max_calls=3)
        self.assertEqual(free.choose(belief, 3), "INSPECT_A")
        self.assertEqual(paid.choose(belief, 3), "INSPECT_A")
        self.assertEqual(free.value(belief, 3), Q(99, 100))
        self.assertEqual(paid.value(belief, 3), Q(89, 100))

    def test_horizon_exhaustion_requires_explicit_finalization(self):
        planner = ExactPlanner("N", max_calls=1)
        clean = normalize(((State((1, 1)), Q(1)),))
        damaged = normalize(((State((1, 1), "none", True), Q(1)),))
        self.assertEqual(planner.value(clean, 0), 0)
        self.assertEqual(planner.value(clean, 1), 1)
        self.assertEqual(planner.value(damaged, 0), -Q(1, 2))
        self.assertEqual(planner.value(damaged, 1), Q(1, 2))

    def test_simultaneous_symbol_renaming_changes_no_value(self):
        for branch in ("N", "C", "F"):
            planner = ExactPlanner(branch, max_calls=3)
            for code in ONE_SYMBOL_CODES:
                renamed = tuple("b" if word == "a" else "a" for word in code)
                self.assertEqual(partition(code), partition(renamed))
                self.assertEqual(planner.code_value(code), planner.code_value(renamed))

    def test_framing_bytes_and_version_rejection(self):
        self.assertEqual(pack_frame(""), b"\x00\x00")
        self.assertEqual(pack_frame("a"), b"\x00\x01a")
        self.assertEqual(pack_frame("ab", 1), b"\x01\x02ab")
        self.assertEqual(deployment_bytes(NO_CODE), 0)
        self.assertEqual(deployment_bytes(SOURCE_CODE), 8)
        self.assertEqual(deployment_bytes(SUFFICIENT_CODE), 12)
        self.assertEqual(deployment_frames(SOURCE_CODE, 1), (b"\x01\x04aabb", b"\x01\x00"))
        with self.assertRaises(ValueError):
            unpack_frame(pack_frame("a", 1), expected_version=0)
        with self.assertRaises(ValueError):
            unpack_frame(b"\x00\x02a")

    @staticmethod
    def accounting_inputs():
        # Synthetic exact values test accounting, not environment performance.
        source = {c: Q(3, 5) for c in ONE_SYMBOL_CODES}
        target = {c: Q(2, 5) for c in ONE_SYMBOL_CODES}
        xor = ("a", "b", "b", "a")
        shifted = ("a", "b", "a", "b")
        source[SOURCE_CODE] = source[xor] = Q(1)
        target[SOURCE_CODE], target[xor], target[shifted] = Q(1, 2), Q(7, 10), Q(9, 10)
        source[NO_CODE], target[NO_CODE] = Q(3, 10), Q(2, 5)
        source[SUFFICIENT_CODE], target[SUFFICIENT_CODE] = Q(19, 20), Q(1)
        metrics = {c: {"success": Q(1), "hazard": Q(0)} for c in target}
        return source, target, metrics

    def test_common_lifecycle_charges_both_phases_and_migration(self):
        source, target, metrics = self.accounting_inputs()
        row = make_row("C", Q(1, 100), Q(1, 10), Q(1), 10, source, target, metrics)
        # 10 source jobs + 10 target jobs; three wire bytes per job;
        # eight deployment bytes initially, another eight at migration;
        # one utility unit of additional migration cost, charged once.
        expected = (10 * Q(1) + 10 * Q(9, 10) - 20 * 3 * Q(1, 100)
                    - 16 * Q(1, 100) - Q(1)) / 20
        self.assertEqual(row["forced_lifecycle"], expected)
        self.assertEqual(expected, Q(431, 500))
        self.assertEqual(row["source_optimal_code_count"], 2)
        self.assertEqual(row["retained_target_min"], Q(47, 100))
        self.assertEqual(row["retained_target_max"], Q(67, 100))
        self.assertEqual(row["best_static_lifecycle"], Q(102, 125))
        self.assertEqual(row["sufficient_lifecycle"], Q(929, 1000))

    def test_costly_forced_switch_is_negative_optional_can_retain(self):
        source, target, metrics = self.accounting_inputs()
        row = make_row("C", Q(1, 100), Q(1, 10), Q(10), 10, source, target, metrics)
        self.assertLess(row["forced_gain_max"], 0)
        self.assertEqual(row["optional_gain_min"], 0)
        self.assertEqual(row["optional_gain_max"], 0)
        self.assertEqual(row["optional_lifecycle_min"], row["retained_lifecycle_min"])
        self.assertEqual(row["optional_lifecycle_max"], row["retained_lifecycle_max"])

    def test_no_change_optional_gain_is_exactly_zero(self):
        source, _, metrics = self.accounting_inputs()
        row = make_row("N", Q(1, 100), Q(1, 10), Q(1), 100, source, source, metrics)
        self.assertEqual(row["optional_gain_min"], 0)
        self.assertEqual(row["optional_gain_max"], 0)
        self.assertLess(row["forced_gain_max"], 0)


if __name__ == "__main__":
    unittest.main()
