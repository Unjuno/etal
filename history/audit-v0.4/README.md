# ETAL historical audit and protocol v0.4

- [Research protocol](ETAL_research_plan_v0_4.md): design proposal, not preregistered.
- [Audit report](ETAL_audit_report_2026_11_26.md): existing-log aggregation, limitations and negative results.
- [Prior art](references/prior_art.csv) and [search log](references/search_log.md).
- [Recomputed principal contrasts](analysis/audit_contrasts.csv) and [input provenance](audit/input_provenance.json).
- [Original experiment plan](inputs/ETAL_original_protocol_v0_1.md) and [reported results](inputs/ETAL_final_report.md).

The historical audit does not constitute new model training or independent container replay. No claim of priority or validated performance gain is made.

## Recompute historical audit

Obtain the exact original archive from its owner (SHA-256 in input_provenance.json) and place it at inputs/ETAL_original_reproducibility.zip. From this directory, in a separate environment:

```sh
python -m pip install -r requirements_audit.txt
python scripts/unpack_original.py
python audit/recompute_audit.py
python scripts/planning_numbers.py
```

The audit script reads the original archive and writes a new audit_recomputed.json locally. The public repository does not yet include the raw archive, model weights, or all ancillary historical artifacts. See [publication policy](../../docs/PUBLICATION.md).
