# G0-1 independent review record

**Review date: 2026-11-26 (Japan time). Scope: the finite G0-1 development diagnostic, not neural learning or G2 confirmation.**

## 1. Judgment and evidence

**No blocking defect was identified in the reviewed environment, exact planner, or lifecycle accounting.** The finite diagnostic provides sufficient evidence to proceed to a separately specified learning development stage. It does not demonstrate learned language evolution.

The reviewer was separate from the environment and solver implementers. The review read the frozen [protocol](../protocols/g01.json), [finite environment](../src/etal/stateful.py), [SQLite implementation](../src/etal/sqlite_backend.py), [planner and accounting](../src/etal/sequential.py), [runner](../src/etal/run_g01.py), both new test modules, and the saved results. It independently reran the existing 14 environment tests and 9 oracle tests; all passed. No new production code or tests were written by this reviewer.

The protocol was published in [commit c37c867](https://github.com/Unjuno/etal/commit/c37c867cf3479daf2ac7765c25d2182c9540bf07) before the reported grid outputs. Its recorded SHA-256 is `0ff01a0a4b209af781ef90fa1caaaa2499e377e3a43fab999f436b25a958fe74`. Exact source and result hashes are in the [manifest](../results/g01/manifest.json). A hash identifies bytes; it does not independently establish execution order or serve as a formal proof.

This is a code review with arithmetic checks and independently implemented backend execution, not an independent formal verification of the complete solver. The backend shares the validated `State` data container, but does not call the finite transition function. The independent oracle test evaluates the planner's chosen actions using SQLite and its own utility accumulation; it still relies on the planner to supply those actions and belief updates.

## 2. Environment and information boundaries

The following properties match the protocol:

- A failed call leaves its previous effects in place. A pre-write failure and a lost post-commit acknowledgement both return `TIMEOUT`, while their persisted records can differ.
- SQLite commits the record transaction before the simulated acknowledgement loss. The implementation does not invent a partially committed atomic SQLite transaction.
- The receiver selects individual writes, inspections, repairs, and finalization. Repair affects only one record, consumes a call, and preserves irreversible damage.
- C **swaps** the append/idempotent contracts of A and B. It changes actual transition consequences while preserving the initial distribution and scoring rules. It is not a one-sided loss of idempotency.
- F changes only the initial prior. Its transition function is identical to N's. Later visited-state distributions are allowed to differ across policies.
- The sender obtains exact local receipt strings once at initialization. The future first-write fault and damage flag are not sender inputs. The receiver acts on the message and its public observation history.
- No-communication policies have the same paid inspection actions as the other policies.
- Explicit `FINALIZE` is required and consumes a call. Horizon exhaustion receives no success reward. Damage is charged once at terminal scoring.

The jobs begin from a synthetic partially completed handoff. Recovery after that handoff is genuinely sequential; the preceding actions that created the initial partial state are not learned in this diagnostic.

The information checks are **structural software checks**, not operating-system isolation. Evaluator-only states and logs exist in the same process. There are no neural weights, gradients, shared optimizer statistics, or checkpoint exchanges to audit here. A later learning implementation must separately enforce within-job weight freezing and audit completed-job update data. The sender helper's documented initialization-only use is followed by the planner; a dedicated type system does not prevent another future caller from misusing it as a refreshed sensor.

## 3. Planner and accounting

The belief recursion enumerates the finite actions and public observations with exact rational probabilities. The receiver knows the branch's transition model and prior, but not the sampled hidden state. This is model-based oracle knowledge, supplied equally to the compared receiver policies.

All source-optimal one-symbol codecs are retained when reporting post-change outcomes. The best fixed codec is selected for the common, equally weighted source/target lifecycle, and its receiver is optimally readapted in each phase. Thus the static control is not weakened by freezing its action policy. The sufficient fixed and no-communication controls are also included.

Serialization and modeled accounting agree:

| Method | Bytes in each job's frame | Initial codebook deployment bytes |
|---|---:|---:|
| One-symbol codec | 3 | 8 |
| Two-symbol sufficient codec | 4 | 12 |
| Empty-payload/no-communication codec | 2 | 0 |

An explicit forced switch pays deployment and the extra assumed update fee even when switching is unnecessary. Optional adaptation may retain the old code, so its gain over retention cannot be negative by construction. Negative forced-switch regions and comparisons against the stronger static controls are therefore essential.

Initial deployment is charged once over both phases. Migration is charged once over the target phase and then included in the common lifecycle average. The extra update fee is a sensitivity parameter, **not** a measured learning or synchronization cost. Frames are serialized to bytes, but no network transport or distributed synchronization timing was measured.

Policy ties use the prospectively specified lexical action order. The reported worst hazard across target-optimal codecs spans codebook ties under that fixed policy rule; it is not a maximization over every equally optimal action policy.

## 4. Observed results

The [complete grid](../results/g01/grid.csv) contains all 243 specified cells. The [summary](../results/g01/summary.json) reports:

| Forced-switch gain over retaining a source-optimal codec | Cells |
|---|---:|
| Positive for every source-code tie | 40 |
| Negative for every source-code tie | 177 |
| Exactly zero for every source-code tie | 18 |
| Other outcomes dependent on the source-code tie | 8 |

These are descriptive counts over a chosen parameter grid, not independent statistical observations or estimates of how often adaptation benefits real systems. Optional adaptation has zero gain across all source ties in 195 cells. Twelve cells have positive lifecycle advantage over all three static controls, before applying the stricter prospective selection rule.

The selection rule chooses C with inspection cost 0.1, byte cost 0.05, extra update fee 1, and 100 jobs in each phase. All costs and utilities below are dimensionless normalized model quantities. The source-optimal partition distinguishes A's initial receipt; the target-optimal partition distinguishes B's receipt. Each partition has two equivalent symbol namings.

| Selected condition: complete source/target lifecycle | Mean utility per job |
|---|---:|
| Optional adaptive oracle, including initial deployment and migration | 0.801 |
| Best single static one-symbol code | 0.763 |
| Fixed sufficient two-symbol code | 0.767 |
| No communication with paid inspection access | 0.760 |
| Adaptive advantage over the strongest listed static control | 0.034 |

In the target phase alone, the adaptive oracle scores 0.796 after its migration charge, compared with 0.720 for the retained source-optimal codec: a modeled difference of 0.076. Migration costs 1.4 normalized utility units in total: 0.4 for eight serialized bytes and 1 for the additional assumed update fee. Both target-optimal code namings achieve success probability 1 and hazard probability 0 under the finite enumerated distribution.

The [representative traces](../results/g01/representative_traces.json) expose a useful but restrictive strategy: under C, the policy first writes to idempotent A, retrying a timeout safely. This consumes the one-use first-write fault before any necessary append to B. B's initial receipt determines whether that later append is needed. The resulting performance depends on this known one-use fault structure; it should not be generalized to repeated faults, unknown fault placement, or arbitrary tools.

The finite probabilities are exhaustively enumerated, so these scores have no Monte Carlo sampling error. That does not eliminate model misspecification, implementation risk, or uncertainty about learning the policy and codec from experience. Zero modeled hazard is not an empirical safety guarantee for a future learned model.

## 5. Validation coverage

| Evidence | Coverage and result | What it establishes |
|---|---|---|
| Environment test suite | 14 tests passed; 819 atomic state/action/branch comparisons and 36 multi-step trajectories | Contract consistency between the finite transition function and independently implemented SQLite mutations |
| Oracle test suite | 9 tests passed; includes 108 SQLite policy/world executions | Small-horizon hand arithmetic, independently accumulated realized policy value, public-history action consistency, fees, framing, finalization, and renaming checks |
| Complete diagnostic runner | 576 SQLite jobs and 2,085 atomic calls; zero recorded mismatches | All target-optimal one-symbol ties plus no-communication and sufficient controls, across the nine branch/inspection settings |

These execution counts come from different checks and include overlapping cases; they must not be added and presented as unique independent samples. SQLite validation is an implementation check of the finite tool contract, not learned-policy transfer or online adaptation in an external tool service.

The [runtime record](../results/g01/runtime.json) identifies Python 3.12.14, SQLite 3.53.1, CPU execution on an Intel Xeon Platinum 8573C, a single process, and uncontrolled clock conditions. Batch size is not applicable to the exact enumeration. The recorded wall time is run provenance, not an inference-speed benchmark. Docker was not executed in that local run; subsequent CI container validation is recorded separately in [reproduction instructions](REPRODUCIBILITY.md). The recorded Git parent identifies the checkout base; executed source bytes are identified separately by the manifest hashes.

## 6. Gate disposition

These are review recommendations scoped to the evidence above, not claims that GitHub issues have already been closed.

| Gate or issue | Recommended status | Reason and remaining scope |
|---|---|---|
| Q1 / finite G0 information-value calibration | Complete for this finite diagnostic | Positive, neutral, and cost-dominated regions are retained; full static controls and update fees are included; the prospective selected-cell rule is met. Empirical learning and migration costs remain unmeasured. |
| Q2 / finite consequence-versus-frequency isolation | Complete for this finite diagnostic | N/C initial distributions and scoring agree; C changes transition semantics; F changes only the initial prior. Practical observational uncertainty and other fault models remain extensions. |
| Q3 / information boundary | Partially complete | Observation construction and public-history consistency are checked. OS isolation, neural update boundaries, shared memory, and distributed synchronization are not implemented or tested. |
| G1 / learned basic skill | Pending | No model was trained. This does not meet the v0.4 development seed-block/fold readiness criteria. |
| G2 / confirmatory adaptation experiment | Pending | No independent confirmatory seeds, learned adaptation comparison, empirical hazard interval, or measured complete update ledger. |
| G3 / learned real-tool transfer and adaptation | Pending | SQLite contract validation alone does not satisfy fixed learned-policy transfer or online adaptation requirements. |
| G4 / evolutionary search, learned chunks, small language models | Pending | These mechanisms are not present in G0-1. |

## 7. Claims to retain and claims to defer

**Supported within the stated model:** changing operation consequences can change which private distinction is worth communicating; after charging modeled transmission and migration costs, adapting that distinction can outperform the stated fixed-code controls in a prospectively selected region. Other regions make forced updating detrimental.

**Not tested:** learned language emergence or evolution, small-model training efficiency, integer-ID advantages, whether emojis or unpronounceable symbols are harmful, natural-language dialects, learned multi-symbol chunks, inference speedups, real synchronization costs, and behavior under imperfect sender logs. Renaming invariance tests demonstrate only that a consistent a/b label permutation leaves this from-scratch finite model unchanged.

The appropriate next stage is a prospectively specified learning development experiment with a source-skill gate, updates restricted to completed jobs, matched comparison groups, seed-level learning curves, and empirical update-cost records. An oracle-controlled actor paired with a codec-search bandit would be a narrower search diagnostic, not a substitute for that stage.
