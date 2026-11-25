"""Finite stateful write/recovery diagnostic (G0-1).

This is a deliberately small *exact-receipt* diagnostic, not a language model
benchmark or a realistic noisy-log inference task.  The coordinator sees only
tool feedback.  A sender's one initial observation contains two local commit
receipts, but not the future fault tape.  The external evaluator owns State.

In N/F, A appends and B is idempotent.  C swaps these transition semantics;
the initial N/C distribution and the success/hazard definitions are unchanged.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import product

ACTIONS = (
    "WRITE_A", "WRITE_B", "INSPECT_A", "INSPECT_B",
    "REPAIR_A", "REPAIR_B", "FINALIZE",
)
NONTERMINAL_ACTIONS = ACTIONS[:-1]
FAULTS = ("none", "pre", "ack")
BRANCHES = ("N", "C", "F")
FAULT_WEIGHTS = (Fraction(1, 2), Fraction(1, 4), Fraction(1, 4))


@dataclass(frozen=True)
class State:
    """Evaluator state, never an input to a receiver policy.

    Counts saturate at two because only absence, uniqueness and duplication
    matter in this finite diagnostic.  Damage records any duplicate event and
    survives repair.  pending_fault is a hidden one-use first-WRITE fault.
    """

    counts: tuple[int, int]
    pending_fault: str = "none"
    damaged: bool = False

    def __post_init__(self):
        if (type(self.counts) is not tuple or len(self.counts) != 2
                or any(type(c) is not int or c not in (0, 1, 2)
                       for c in self.counts)):
            raise ValueError("counts must be a pair of integers in [0, 2]")
        if self.pending_fault not in FAULTS:
            raise ValueError("unknown pending fault")
        if type(self.damaged) is not bool:
            raise ValueError("damaged must be boolean")
        if 2 in self.counts and not self.damaged:
            raise ValueError("a duplicate count requires irreversible damage")


def check_branch(branch: str) -> None:
    if branch not in BRANCHES:
        raise ValueError("branch must be N, C or F")


def step(state: State, action: str, branch: str):
    """Execute one atomic tool call without resetting any previous progress.

    A pre-commit failure and a lost post-commit acknowledgement both return
    TIMEOUT.  Only a WRITE consumes the pending fault; inspection and repair
    leave it pending.  Repair resets one record to zero and costs a separate
    call; a subsequent WRITE is still needed.  FINALIZE does not certify success
    to the actor: the external evaluator checks the resulting persisted state.
    """
    check_branch(branch)
    if action not in ACTIONS:
        raise ValueError("unknown action")
    if action == "FINALIZE":
        return state, "DONE", True
    index = 0 if action.endswith("_A") else 1
    if action.startswith("INSPECT_"):
        return state, f"COUNT={state.counts[index]}", False
    counts = list(state.counts)
    if action.startswith("REPAIR_"):
        counts[index] = 0
        return State(tuple(counts), state.pending_fault, state.damaged), "OK", False
    if state.pending_fault == "pre":
        return State(state.counts, "none", state.damaged), "TIMEOUT", False
    append_index = 1 if branch == "C" else 0
    if index == append_index:
        counts[index] = min(2, counts[index] + 1)
    else:
        counts[index] = max(1, counts[index])
    damaged = state.damaged or counts[index] == 2
    observation = "TIMEOUT" if state.pending_fault == "ack" else "OK"
    return State(tuple(counts), "none", damaged), observation, False


def initial_worlds(branch: str):
    """Return exact joint masses of initial records and first-WRITE fault.

    N/C: independent fair initial commit receipts.  F alone raises probability
    that A is absent from 1/2 to 3/4.  Fault probabilities remain identical.
    All branches use the same twelve possible world states.
    """
    check_branch(branch)
    probability_a_zero = Fraction(3, 4) if branch == "F" else Fraction(1, 2)
    worlds = []
    for a, b in product((0, 1), repeat=2):
        pa = probability_a_zero if a == 0 else 1 - probability_a_zero
        for fault, pf in zip(FAULTS, FAULT_WEIGHTS):
            worlds.append((State((a, b), fault), pa * Fraction(1, 2) * pf))
    return tuple(worlds)


def sender_observation(state: State) -> tuple[str, str]:
    """Initial sender-local receipts; future fault and damage are not fields.

    Exact initial receipts are an explicit G0 simplification.  This function
    must not be reused as a privileged sensor after each action or advertised
    as a noisy/raw-log inference benchmark.
    """
    if any(c not in (0, 1) for c in state.counts):
        raise ValueError("sender receipts are defined only for initial counts")
    return tuple(
        f"record={name};local_commit={'yes' if count else 'no'}"
        for name, count in zip(("A", "B"), state.counts)
    )


def observation_index(observation: tuple[str, str]) -> int:
    """Stable encoder-table index, 2*A + B, computed only from receipts."""
    if type(observation) is not tuple or len(observation) != 2:
        raise ValueError("expected the pair of initial receipt strings")
    values = []
    for name, receipt in zip(("A", "B"), observation):
        if receipt == f"record={name};local_commit=no":
            values.append(0)
        elif receipt == f"record={name};local_commit=yes":
            values.append(1)
        else:
            raise ValueError("unknown receipt format")
    return 2 * values[0] + values[1]


def success(state: State) -> bool:
    """Final goal only; safe success additionally requires not state.damaged."""
    return state.counts == (1, 1)


def all_states():
    """All valid states, including initially unreachable recovery states."""
    for counts in product(range(3), repeat=2):
        for fault in FAULTS:
            for damaged in (False, True):
                if 2 not in counts or damaged:
                    yield State(counts, fault, damaged)
