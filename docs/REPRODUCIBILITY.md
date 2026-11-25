# Development reproduction (G0-0)

The current code uses the Python standard library only (3.10+). It is a finite one-decision oracle, not a learned model or the full sequential G0 gate.

From repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m etal.g0 --out /tmp/g0_grid.csv
cmp results/g0_grid.csv /tmp/g0_grid.csv
```

The committed reference grid contains 864 cells. Original local run metadata and logs are in [results](../results/).

Container smoke-test recipe (Dockerfile supplied; not validated at initial import; base tag not frozen):

```sh
docker build -t etal-g0:dev .
docker run --rm --network=none --read-only etal-g0:dev
docker run --rm --network=none --read-only --tmpfs /tmp etal-g0:dev sh -c 'python -m etal.g0 --out /tmp/g0_grid.csv && cmp results/g0_grid.csv /tmp/g0_grid.csv'
```

Before any confirmatory run, freeze the source commit, image digest, dependency lock, configuration, independent evaluator and seed-generation rule. Keep failed seeds and report all costs. See the [proposed protocol](../history/audit-v0.4/ETAL_research_plan_v0_4.md).
