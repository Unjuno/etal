# Public research and reproducibility policy

- Keep the audited v0.4 proposal unchanged in `history/`. Record modifications as new protocols, with date, rationale, affected hypotheses, code commit, and whether the relevant outcome was already seen.
- Keep development, confirmation, fixed transfer and real-tool online adaptation results separate. No post hoc removal of unsuccessful seeds. Commit null and negative results with positive results.
- Use a fresh branch/PR for an environment, model, or metric change. Link the relevant Issue ID and log command, config digest, seed and measured runtime. No claim of passing a gate merely because tests pass.
- Use read-only CI permissions by default. The initial workflow performs only a deterministic diagnostic and unit tests. Long training and credential-bearing publishing are manual operations.
- Do not commit private file paths, tokens, personal information, raw conversations or credentials. Large logs and model weights should be independently checked, archived by digest, and published only after content/rights review. No third-party full-text papers are included.
- The code/data license remains undecided. Public access is requested; reuse permission is not presumed. Establish license and citation metadata before accepting outside code contributions.
