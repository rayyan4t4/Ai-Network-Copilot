# Controlled study dataset

All observations were acquired in the isolated four-site emulated laboratory. Private-range addresses and generic node names are laboratory identifiers, not production traffic or customer information.

- `final/`: 70 independently acquired final windows; ten of each of five faults, ten healthy and ten insufficient-evidence cases.
- `pilot/`: separate calibration attempts and retained pilot failures, excluded from final denominators.
- `control/`: labels, injection/restore acknowledgements, schedules and attempt accounting. Diagnostic inputs must never read this directory.
- `results.json` / `results.csv`: original aggregate and row-level results, including failures.
- `reference-freeze.json`: original experiment source hashes and resource amendment lineage.
- `release-source-lock.json`: hash lock for the renamed release, created after the study.
- `migration-provenance.json`: original-to-release file mapping and source hashes.

Each final case contains `original.json` (untouched capture), `observations.json` (actual diagnostic copy), `analysis.json`, and `B1.json`, `B2.json`, `no_gate.json`, `full.json`. Insufficient cases withhold observations from the diagnostic copy; the original remains separately retained. Requests contain normalized summaries, not injection labels or credentials. All four approaches share the same observation-file SHA256.

Run `python app.py verify` to recompute objective outcome counts and verify all 490 final-case file hashes without modifying them or making cloud requests. Migration tests also confirm the same reconstructed model inputs and direct-alert predictions.

Later browser viewing and demonstration feedback are new operational activity. They must not be used to backfill the original incident-to-display latency or independent human judgments. Two real reviewer assessments remain pending.
