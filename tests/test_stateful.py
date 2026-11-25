import ast
from fractions import Fraction
from itertools import product
from pathlib import Path
import sqlite3
import unittest

from etal.stateful import (
    ACTIONS, FAULTS, State, all_states, initial_worlds, observation_index,
    sender_observation, step, success,
)
from etal.sqlite_backend import SQLiteBackend


class TestStatefulContract(unittest.TestCase):
    def test_c_preserves_initial_worlds_exactly(self):
        self.assertEqual(initial_worlds("N"), initial_worlds("C"))
        for branch in ("N", "C", "F"):
            worlds = initial_worlds(branch)
            self.assertEqual(len(worlds), 12)
            self.assertEqual(sum(p for _, p in worlds), 1)
            self.assertEqual(sum(p for s, p in worlds if s.pending_fault == "pre"), Fraction(1, 4))
        self.assertNotEqual(initial_worlds("N"), initial_worlds("F"))
        self.assertEqual(sum(p for s, p in initial_worlds("F") if s.counts[0] == 0), Fraction(3, 4))

    def test_f_changes_no_transition(self):
        for state, action in product(all_states(), ACTIONS):
            self.assertEqual(step(state, action, "N"), step(state, action, "F"))

    def test_c_changes_only_write_consequences(self):
        for state in all_states():
            for action in ("INSPECT_A", "INSPECT_B", "REPAIR_A", "REPAIR_B", "FINALIZE"):
                self.assertEqual(step(state, action, "N"), step(state, action, "C"))
        state = State((1, 1))
        self.assertEqual(step(state, "WRITE_A", "N")[0], State((2, 1), "none", True))
        self.assertEqual(step(state, "WRITE_A", "C")[0], state)
        self.assertEqual(step(state, "WRITE_B", "N")[0], state)
        self.assertEqual(step(state, "WRITE_B", "C")[0], State((1, 2), "none", True))

    def test_pre_and_ack_have_same_feedback_different_persistence(self):
        pre = step(State((0, 0), "pre"), "WRITE_A", "N")
        ack = step(State((0, 0), "ack"), "WRITE_A", "N")
        self.assertEqual(pre[1:], ack[1:])
        self.assertEqual(pre[0].counts, (0, 0))
        self.assertEqual(ack[0].counts, (1, 0))
        # A retry after the missing acknowledgement produces a real duplicate.
        retry = step(ack[0], "WRITE_A", "N")
        self.assertEqual(retry[0], State((2, 0), "none", True))

    def test_repair_does_not_reset_job_or_clear_hazard(self):
        state = State((2, 1), "ack", True)
        repaired, obs, terminal = step(state, "REPAIR_A", "N")
        self.assertEqual(repaired, State((0, 1), "ack", True))
        self.assertEqual((obs, terminal), ("OK", False))
        rewritten, _, _ = step(repaired, "WRITE_A", "N")
        self.assertTrue(success(rewritten))
        self.assertTrue(rewritten.damaged)

    def test_sender_observation_has_no_future_fault_or_damage(self):
        for counts in product((0, 1), repeat=2):
            observations = {
                sender_observation(State(counts, fault, damaged))
                for fault, damaged in product(FAULTS, (False, True))
            }
            self.assertEqual(len(observations), 1)
            observation = observations.pop()
            self.assertEqual(observation_index(observation), 2 * counts[0] + counts[1])
            self.assertTrue(all(type(x) is str for x in observation))
            self.assertFalse(any("fault" in x or "damaged" in x for x in observation))

    def test_inspection_is_available_and_unchanged_for_all_conditions(self):
        for branch, state in product(("N", "C", "F"), all_states()):
            for i, action in enumerate(("INSPECT_A", "INSPECT_B")):
                new_state, observation, terminal = step(state, action, branch)
                self.assertEqual(new_state, state)
                self.assertEqual(observation, f"COUNT={state.counts[i]}")
                self.assertFalse(terminal)

    def test_finalization_does_not_leak_success_to_actor(self):
        for state in all_states():
            self.assertEqual(step(state, "FINALIZE", "N"), (state, "DONE", True))

    def test_validation_prevents_ambiguous_or_invalid_inputs(self):
        for counts in ((True, 0), (3, 0), [0, 0], (0,)):
            with self.assertRaises(ValueError):
                State(counts)
        with self.assertRaises(ValueError):
            State((2, 0))
        with self.assertRaises(ValueError):
            observation_index(("A:secret", "B:secret"))
        with self.assertRaises(ValueError):
            step(State((0, 0)), "WRITE_C", "N")
        with self.assertRaises(ValueError):
            initial_worlds("unknown")


class TestSQLiteBackend(unittest.TestCase):
    def test_independent_backend_has_no_finite_transition_call(self):
        import etal.sqlite_backend as implementation
        tree = ast.parse(Path(implementation.__file__).read_text())
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(
            [alias.name for node in imports if node.module == "stateful" for alias in node.names],
            ["State"],
        )

    def test_exhaustive_single_step_state_action_equivalence(self):
        checked = 0
        for branch, state, action in product(("N", "C", "F"), tuple(all_states()), ACTIONS):
            expected, observation, terminal = step(state, action, branch)
            with SQLiteBackend(state, branch) as backend:
                self.assertEqual(backend.step(action), (observation, terminal))
                self.assertEqual(backend.snapshot(), expected)
            checked += 1
        self.assertEqual(checked, 819)

    def test_commit_is_persisted_before_ack_loss(self):
        with SQLiteBackend(State((0, 0), "ack"), "N") as backend:
            self.assertEqual(backend.step("WRITE_A"), ("TIMEOUT", False))
            with sqlite3.connect(backend.database_path) as reader:
                count = reader.execute("SELECT COUNT(*) FROM records WHERE record = 'A'").fetchone()[0]
            self.assertEqual(count, 1)
            phases = [row[2] for row in backend.event_log()]
            self.assertEqual(phases, ["write_transaction_commit", "after_commit_ack_lost"])

    def test_pre_failure_leaves_rows_unchanged(self):
        with SQLiteBackend(State((0, 1), "pre"), "N") as backend:
            backend.step("WRITE_A")
            self.assertEqual(backend.snapshot(), State((0, 1)))
            self.assertEqual([row[2] for row in backend.event_log()], ["before_write_transaction"])

    def test_multi_step_recovery_and_persisted_damage(self):
        actions = ("WRITE_A", "INSPECT_A", "WRITE_A", "REPAIR_A", "WRITE_A",
                   "INSPECT_B", "WRITE_B", "FINALIZE")
        for branch in ("N", "C", "F"):
            for initial, _ in initial_worlds(branch):
                state = initial
                with SQLiteBackend(initial, branch) as backend:
                    for action in actions:
                        state, observation, terminal = step(state, action, branch)
                        self.assertEqual(backend.step(action), (observation, terminal))
                        self.assertEqual(backend.snapshot(), state)
                    with self.assertRaises(RuntimeError):
                        backend.step("WRITE_A")


if __name__ == "__main__":
    unittest.main()
