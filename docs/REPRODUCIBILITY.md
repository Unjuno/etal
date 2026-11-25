# Reproduction: finite G0-0 and sequential G0-1

The scientific calculations use only Python's standard library (Python 3.10+ including SQLite). G0-1 is exact finite belief-state planning, **not neural training**. The historical original experiment and audit have their own dependencies and are separate.

## Local reproduction

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m etal.g0 --out /tmp/g0_grid.csv
cmp results/g0_grid.csv /tmp/g0_grid.csv
PYTHONPATH=src python -m etal.run_g01 --out /tmp/etal-g01
cmp results/g01/grid.csv /tmp/etal-g01/grid.csv
cmp results/g01/codec_metrics.csv /tmp/etal-g01/codec_metrics.csv
cmp results/g01/summary.json /tmp/etal-g01/summary.json
cmp results/g01/representative_traces.json /tmp/etal-g01/representative_traces.json
```

The original G0-0 reference grid has 864 cells. G0-1 has 243 cells, with all 12 initial worlds enumerated. The runner also evaluates target-optimal codec ties and two controls through the independent SQLite implementation: 576 policy/world jobs and 2,085 atomic calls. These deterministic results must reproduce exactly; run times and timestamps will differ.

G0-1 was initially evaluated after [prospective protocol commit c37c867](https://github.com/Unjuno/etal/commit/c37c867cf3479daf2ac7765c25d2182c9540bf07). That is a development-stage freeze, not G2 registration. Source and result hashes are in `results/g01/manifest.json`; hardware, Python, SQLite and execution command are in `results/g01/runtime.json`. The runtime's `parent_git_head` records the checkout at execution; modified source is identified by the separate SHA-256 manifest.

Optional figure generation uses matplotlib; the executed plotting environment used matplotlib 3.10.8. It is not needed for the calculations or tests:

```sh
python scripts/plot_g01.py
```

## Container reproduction

The local environment used for initial computation had no Docker or Podman executable. GitHub Actions [run 45714233529](https://github.com/Unjuno/etal/actions/runs/45714233529), at commit `afdbe1bd27b0fddac7f3cf70759521ca20df0cb6`, **successfully built and executed the container**. All 33 tests and all four deterministic G0-1 result comparisons passed both on the host and inside the container. The evidence is also summarized in [ci_validation.json](../results/g01/ci_validation.json). This is the finite diagnostic, not a model-training container.

```sh
docker build -t etal-g01:dev .
docker run --rm --network=none --read-only --cpus=1 --memory=512m --tmpfs /tmp:rw,nosuid,nodev,size=64m etal-g01:dev
docker run --rm --network=none --read-only --cpus=1 --memory=512m --tmpfs /tmp:rw,nosuid,nodev,size=64m etal-g01:dev sh -c 'python -m etal.run_g01 --out /tmp/g01 && cmp results/g01/grid.csv /tmp/g01/grid.csv && cmp results/g01/codec_metrics.csv /tmp/g01/codec_metrics.csv && cmp results/g01/summary.json /tmp/g01/summary.json && cmp results/g01/representative_traces.json /tmp/g01/representative_traces.json'
```

The image runs as unprivileged UID/GID 65534, with writable temporary SQLite files only in the supplied tmpfs. The base is pinned to `python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b`, resolved in the first observed CI build. The workflow records the built image ID; the base digest is in the Dockerfile and build log. No GPU, pretrained model, external API or network is used by the experiment.

The first expanded CI attempt, [run 45713810886](https://github.com/Unjuno/etal/actions/runs/45713810886), passed all 33 host tests, both exact reproductions and the container build. It then stopped because `docker image inspect python:3.12-slim` assumed that BuildKit had separately registered the base tag in the Docker image store. The fix pins the digest already observed in the successful build and inspects only the built experiment image. This metadata failure did not change the experimental code or results; the failed run remains public.

Before any confirmatory run, freeze the source commit, base image digest, dependency lock, configuration, independent evaluator and seed-generation rule. Keep failed runs and report all costs. See the [v0.4 proposal](../history/audit-v0.4/ETAL_research_plan_v0_4.md).

## What the checks do not establish

The sender receives exact initial local receipts; noisy observation inference is untested. The planner knows the transition model; learning and full update cost are unmeasured. SQLite verifies a deliberately finite contract with one injected first-write fault, not actual network loss or power-failure durability. API information boundaries are structural tests, not an OS isolation guarantee. The container's OS limits and the model's observation boundaries address different issues.
