# Research and release provenance

The original implementation was developed in scheduled stages. This repository reorganizes it by component after the controlled study. The renamed source is a new release, not a claim that byte hashes remained identical after imports, paths, configuration and launchers changed.

`research/reference-freeze.json` retains the original pre-trial manifest and resource-only amendment. Its historical paths describe the private reference workspace. `research/migration-provenance.json` maps copied files to their original source hashes. `research/release-source-lock.json` identifies the organized release used by `evaluation.freeze.verify()`; it is a post-study release lock, not a backdated experimental freeze.

All 490 files in the 70 final case directories are copied without rewriting. This includes original/masked observations, analysis and four outputs per case. `scripts/verify_release.py` checks them against the original source hashes and recomputes objective scores. Migration tests also reconstruct every archived model request that is present and all 70 direct-baseline predictions, confirming they agree after reorganization. No new provider calls are required for these checks.

The public records contain only isolated laboratory data, including private-range laboratory addresses and generic device names. They do not represent production traffic or real operational outages. API keys, actual SNMP community values, controller authentication, machine-specific deployment paths, populated database backups, SSH configuration and personal contact details are excluded from the publication set.

Operational fixes after the study include indexed latest-observation views, indexes supporting existing bounded queries and independent live snapshot collection. They improve the current operating path, but the original 70-case metrics were not regenerated under those changes. Original timing boundaries and failures remain disclosed in the report and clarifications.

Opening the archived viewer later may create local display acknowledgements. Such acknowledgements do not establish the original incident-to-display latency. Independent reviewer ratings remain pending; automated QA records are not human research judgments.

The screenshot capture shows the current live application. The archived-viewer origin on port 8766 remained blocked for browser automation during release preparation, although its API and persistence behavior were tested. No screenshot or browser-display timing is invented for that origin.
