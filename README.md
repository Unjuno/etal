# ETAL — Evolutionary Task-Adaptive Language

**Research in progress / 研究中 · v0.0.1 · 2026-11-26 JST**

[![Finite diagnostic tests](https://github.com/Unjuno/etal/actions/workflows/test.yml/badge.svg)](https://github.com/Unjuno/etal/actions/workflows/test.yml)

[Open research issues (Q1–Q9)](https://github.com/Unjuno/etal/issues?q=is%3Aissue+is%3Aopen) · [Current scope and import status](docs/IMPORT_STATUS.md)

**Research question:** When does changing task-grounded communication after a consequence shift yield a net benefit beyond adapting an action policy, including communication, repair, update and synchronization costs?

状態の出現頻度を変えず、操作の帰結だけを変化させたとき、経験から通信の意味区分を更新することに追加価値があるかを調べる。文字ID、創発通信、小型モデル、逐次ツール失敗を研究対象とする。

## Evidence status

- Historical pilot: useful communication in some runs; net improvement from updating communication was **not established**. The audit found weak initial skill, seed concentration and confounded evolutionary comparisons.
- v0.4 research plan: **proposal, not yet preregistered**. Do not treat planned sample sizes or thresholds as validated results.
- G0 starter: exact single-decision diagnostic with four observable states, binary actions, fixed-width messages and a paid perfect-inspection option. **864 grid cells; 10 local tests passed.** It is an oracle calculation, not learned communication, sequential tool execution, wall-clock speed or a full G0 gate.
- G1–G4: not implemented. No claim of novelty priority, improved LLM performance, or container validation.

## Quick start

Python 3.10+; no third-party dependency for the finite diagnostic. Tested in the local CPU runtime; see `results/runtime.json`. From the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m etal.g0 --out results/g0_grid.csv
```

The initial [GitHub Actions run](https://github.com/Unjuno/etal/actions/runs/45696204600) passed the unit tests and exact CSV reproduction. The badge shows the current workflow status. The supplied Dockerfile is a development recipe; Docker execution has not been verified. See [reproduction instructions](docs/REPRODUCIBILITY.md).

## Read in this order

| Path | Purpose |
|---|---|
| [Research protocol v0.4](history/audit-v0.4/ETAL_research_plan_v0_4.md) | Canonical proposed design, hypotheses, gates and decision rules |
| [Prior audit](history/audit-v0.4/ETAL_audit_report_2026_11_26.md) | Negative results, limitations and evidence |
| [Prior art](history/audit-v0.4/references/prior_art.csv) | 22 references and novelty assessment |
| [G0 notes](docs/G0.md) | Diagnostic, assumptions, example results, limits |
| [Nine issues](ISSUES.md) | Live GitHub Issues and acceptance criteria |
| [Release and evidence policy](docs/PUBLICATION.md) | Publication, experiment changes, raw data, licensing |
| [Research protocol config](history/audit-v0.4/configs/research_protocol_v0_4.yaml) | Historical machine-readable proposal with unset fields |

## Roadmap

G0 (information value) → G1 (basic skill) → G2 (locked confirmatory comparison) → G3 (independent tool backends) → G4 (population evolution and learned computation chunks). No gate may be skipped to obtain a favorable result.

## Scope and license

Public research scaffold. A software/data license has not been chosen; public visibility does not grant reuse rights. Decide licensing before inviting redistribution or merging externally licensed code. No external papers or pretrained weights are bundled. Large historical raw logs and weights are not committed. The public import includes the core research materials and audit scripts, but is not a byte-for-byte mirror of the local starter archive; see [import status](docs/IMPORT_STATUS.md).
