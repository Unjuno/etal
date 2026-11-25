"""Exact G0-1 belief-state planning and lifecycle accounting.

The oracle knows the finite transition kernel and prior, not the sampled hidden
state. It enumerates the stated codec class, not all possible dialogue protocols.
Only normalized utility is modeled; CPU time is measured separately by the CLI.
"""
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction as Q
from functools import lru_cache
from itertools import product

from .stateful import (
    ACTIONS, State, initial_worlds, observation_index, sender_observation,
    step, success,
)

ONE_SYMBOL_CODES = tuple(product(("a", "b"), repeat=4))
SUFFICIENT_CODE = ("aa", "ab", "ba", "bb")
NO_CODE = ("",) * 4
ACTION_ORDER = tuple(sorted(ACTIONS))


@dataclass(frozen=True)
class Costs:
    inspect: Q = Q(1, 10)
    write: Q = Q(1, 50)
    repair: Q = Q(1, 10)
    damage: Q = Q(1, 2)

    def __post_init__(self):
        if any(not isinstance(x, (Q, int)) or x < 0
               for x in (self.inspect, self.write, self.repair, self.damage)):
            raise ValueError("costs must be nonnegative exact rationals")

    def action(self, action):
        if action.startswith("WRITE_"):
            return self.write
        if action.startswith("INSPECT_"):
            return self.inspect
        if action.startswith("REPAIR_"):
            return self.repair
        if action == "FINALIZE":
            return Q(0)
        raise ValueError("unknown action")


def state_key(state):
    return state.counts, state.pending_fault, state.damaged


def normalize(worlds):
    weights = defaultdict(Q)
    for state, weight in worlds:
        if weight < 0:
            raise ValueError("negative probability")
        weights[state] += weight
    total = sum(weights.values(), Q(0))
    if not total:
        raise ValueError("empty belief")
    return tuple((state, weight / total) for state, weight in
                 sorted(weights.items(), key=lambda item: state_key(item[0])) if weight)


def validate_code(code):
    if len(code) != 4 or len({len(word) for word in code}) != 1:
        raise ValueError("code must have four equally long codewords")
    if any(any(c not in "ab" for c in word) for word in code):
        raise ValueError("only a/b symbols are permitted")
    if len(code[0]) > 2:
        raise ValueError("at most two symbols in this diagnostic")


def pack_frame(payload, version=0):
    if type(version) is not int or not 0 <= version <= 255:
        raise ValueError("version must fit uint8")
    raw = payload.encode("ascii")
    if len(raw) > 255 or any(c not in b"ab" for c in raw):
        raise ValueError("invalid payload")
    return bytes((version, len(raw))) + raw


def unpack_frame(frame, expected_version=0):
    if len(frame) < 2 or frame[0] != expected_version:
        raise ValueError("missing frame or version mismatch")
    if frame[1] != len(frame) - 2:
        raise ValueError("length mismatch")
    payload = frame[2:].decode("ascii")
    if any(c not in "ab" for c in payload):
        raise ValueError("invalid alphabet")
    return payload


def deployment_frames(code, version=0):
    """Actual serialized codebook plus acknowledgement, no socket claimed."""
    validate_code(code)
    if code == NO_CODE:
        return ()
    return pack_frame("".join(code), version), pack_frame("", version)


def deployment_bytes(code):
    return sum(map(len, deployment_frames(code)))


def partition(code):
    """Canonical equivalence relation, invariant to simultaneous renaming."""
    ids = {}
    return tuple(ids.setdefault(word, len(ids)) for word in code)


class ExactPlanner:
    def __init__(self, branch, costs=Costs(), max_calls=5):
        if type(max_calls) is not int or max_calls < 1:
            raise ValueError("max_calls must be a positive integer")
        self.worlds = initial_worlds(branch)
        self.branch, self.costs, self.max_calls = branch, costs, max_calls
        self.choices = {}
        # Per-instance caches do not retain all preceding grid planners.
        self.transitions = lru_cache(maxsize=None)(self._transitions)
        self.value = lru_cache(maxsize=None)(self._value)

    def terminal_score(self, state, finalized):
        return Q(int(finalized and success(state))) - self.costs.damage * state.damaged

    def _transitions(self, belief, action):
        observed = defaultdict(list)
        for state, weight in belief:
            following, observation, done = step(state, action, self.branch)
            observed[(observation, done)].append((following, weight))
        return tuple((observation, done, sum((w for _, w in worlds), Q(0)),
                      normalize(worlds))
                     for (observation, done), worlds in sorted(observed.items()))

    def _value(self, belief, remaining):
        if remaining == 0:
            return sum((p * self.terminal_score(s, False) for s, p in belief), Q(0))
        best_value, best_action = None, None
        for action in ACTION_ORDER:
            value = -self.costs.action(action)
            for _, done, probability, following in self.transitions(belief, action):
                future = (sum((p * self.terminal_score(s, True)
                               for s, p in following), Q(0)) if done else
                          self.value(following, remaining - 1))
                value += probability * future
            if best_value is None or value > best_value:
                best_value, best_action = value, action
        self.choices[(belief, remaining)] = best_action
        return best_value

    def choose(self, belief, remaining):
        if remaining < 1:
            raise ValueError("no calls left")
        self.value(belief, remaining)
        return self.choices[(belief, remaining)]

    def initial_belief(self, code, message):
        validate_code(code)
        selected = [(state, p) for state, p in self.worlds
                    if code[observation_index(sender_observation(state))] == message]
        return normalize(selected)

    def update(self, belief, action, public_observation):
        for observation, done, probability, following in self.transitions(belief, action):
            if observation == public_observation:
                return following, done
        raise ValueError("observation impossible under the public history")

    def code_value(self, code):
        validate_code(code)
        total = Q(0)
        for message in sorted(set(code)):
            selected = [(s, p) for s, p in self.worlds
                        if code[observation_index(sender_observation(s))] == message]
            probability = sum((p for _, p in selected), Q(0))
            total += probability * self.value(normalize(selected), self.max_calls)
        return total

    def rollout(self, code, initial_state, backend=None):
        """Evaluation-only loop; choose/update receive no sampled state.

        backend, when provided, implements independent step/snapshot methods.
        The sampled state is read only by sender initialization and evaluator.
        """
        message = code[observation_index(sender_observation(initial_state))]
        frame = pack_frame(message)
        belief = self.initial_belief(code, unpack_frame(frame))
        state, finalized, incurred = initial_state, False, Q(0)
        trace = []
        for remaining in range(self.max_calls, 0, -1):
            action = self.choose(belief, remaining)
            before = state
            if backend is None:
                state, observation, finalized = step(state, action, self.branch)
            else:
                observation, finalized = backend.step(action)
                state = backend.snapshot()
            incurred += self.costs.action(action)
            trace.append({"action": action, "observation": observation,
                          "before": state_key(before), "after": state_key(state)})
            if finalized:
                break
            belief, done = self.update(belief, action, observation)
            if done:
                raise AssertionError("unexpected termination")
        return {"utility": self.terminal_score(state, finalized) - incurred,
                "success": int(finalized and success(state)),
                "safe_success": int(finalized and success(state) and not state.damaged),
                "hazard": int(state.damaged), "calls": len(trace),
                "writes": sum(t["action"].startswith("WRITE_") for t in trace),
                "inspections": sum(t["action"].startswith("INSPECT_") for t in trace),
                "repairs": sum(t["action"].startswith("REPAIR_") for t in trace),
                "frame_hex": frame.hex(), "trace": trace}

    def code_metrics(self, code):
        keys = ("utility", "success", "safe_success", "hazard", "calls",
                "writes", "inspections", "repairs")
        totals = {key: Q(0) for key in keys}
        for state, probability in self.worlds:
            result = self.rollout(code, state)
            for key in keys:
                totals[key] += probability * result[key]
        if totals["utility"] != self.code_value(code):
            raise AssertionError("rollout and Bellman values disagree")
        return totals


def make_row(branch, byte_cost, inspect_cost, extra_update_fee, jobs_per_phase,
             source_values, target_values, target_metrics):
    """All comparisons use equal source/target phases and exact fees.

    Values passed in include tools, success, damage; framing and migrations are
    added here. The receiver is an optimal model-based planner for every code.
    No actor learning charge or empirical model update cost is implied.
    """
    if any(x < 0 for x in (byte_cost, inspect_cost, extra_update_fee)):
        raise ValueError("negative cost")
    if type(jobs_per_phase) is not int or jobs_per_phase < 1:
        raise ValueError("invalid horizon")
    h = jobs_per_phase
    codes = ONE_SYMBOL_CODES
    pre = max(source_values[c] for c in codes) - 3 * byte_cost
    source_codes = [c for c in codes if source_values[c] - 3 * byte_cost == pre]
    post = max(target_values[c] for c in codes) - 3 * byte_cost
    target_codes = [c for c in codes if target_values[c] - 3 * byte_cost == post]
    fixed = [target_values[c] - 3 * byte_cost for c in source_codes]
    deployment = deployment_bytes(codes[0]) * byte_cost
    migration = deployment + extra_update_fee
    forced = post - migration / h
    optional = [max(value, forced) for value in fixed]
    fixed_lifecycle = [(pre + value) / 2 - deployment / (2 * h) for value in fixed]
    optional_lifecycle = [(pre + value) / 2 - deployment / (2 * h) for value in optional]
    forced_lifecycle = (pre + forced) / 2 - deployment / (2 * h)
    static_values = {c: (source_values[c] + target_values[c]) / 2 - 3 * byte_cost
                       - deployment / (2 * h) for c in codes}
    static_best = max(static_values.values())
    nc_post = target_values[NO_CODE] - 2 * byte_cost
    nc_lifecycle = (source_values[NO_CODE] + target_values[NO_CODE]) / 2 - 2 * byte_cost
    sufficient_post = target_values[SUFFICIENT_CODE] - 4 * byte_cost
    sufficient_lifecycle = ((source_values[SUFFICIENT_CODE] + target_values[SUFFICIENT_CODE]) / 2
                           - 4 * byte_cost - deployment_bytes(SUFFICIENT_CODE) * byte_cost / (2 * h))
    alternatives = max(static_best, nc_lifecycle, sufficient_lifecycle)
    forced_gains = [forced - value for value in fixed]
    optional_gains = [new - old for new, old in zip(optional, fixed)]
    return {
        "branch": branch, "byte_cost": byte_cost, "inspect_cost": inspect_cost,
        "extra_update_fee": extra_update_fee, "jobs_per_phase": h,
        "source_optimal_code_count": len(source_codes),
        "target_optimal_code_count": len(target_codes),
        "source_optimal_codes": ";".join(",".join(c) for c in source_codes),
        "target_optimal_codes": ";".join(",".join(c) for c in target_codes),
        "source_partition_count": len({partition(c) for c in source_codes}),
        "target_partition_count": len({partition(c) for c in target_codes}),
        "source_per_job": pre, "target_oracle_per_job": post,
        "retained_target_min": min(fixed), "retained_target_max": max(fixed),
        "forced_target": forced, "optional_target_min": min(optional),
        "optional_target_max": max(optional),
        "forced_gain_min": min(forced_gains), "forced_gain_max": max(forced_gains),
        "optional_gain_min": min(optional_gains), "optional_gain_max": max(optional_gains),
        "retained_lifecycle_min": min(fixed_lifecycle),
        "retained_lifecycle_max": max(fixed_lifecycle),
        "forced_lifecycle": forced_lifecycle,
        "optional_lifecycle_min": min(optional_lifecycle),
        "optional_lifecycle_max": max(optional_lifecycle),
        "best_static_lifecycle": static_best,
        "no_communication_target": nc_post, "no_communication_lifecycle": nc_lifecycle,
        "sufficient_target": sufficient_post, "sufficient_lifecycle": sufficient_lifecycle,
        "lifecycle_advantage_min": min(optional_lifecycle) - alternatives,
        "lifecycle_advantage_max": max(optional_lifecycle) - alternatives,
        "initial_deployment_bytes": deployment_bytes(codes[0]),
        "migration_bytes": deployment_bytes(codes[0]), "migration_fee": migration,
        "target_success_min": min(target_metrics[c]["success"] for c in target_codes),
        "target_hazard_max": max(target_metrics[c]["hazard"] for c in target_codes),
    }


def select_cell(rows):
    eligible = [r for r in rows if r["branch"] == "C"
                and r["extra_update_fee"] == 1 and r["jobs_per_phase"] == 100
                and r["lifecycle_advantage_min"] > Q(1, 50)
                and r["forced_gain_min"] > Q(1, 50)
                and r["target_success_min"] == 1 and r["target_hazard_max"] == 0]
    return min(eligible, key=lambda r: (r["byte_cost"], r["inspect_cost"])) if eligible else None
