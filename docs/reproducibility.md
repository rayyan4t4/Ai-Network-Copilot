# Reproducing the research and application

## Verify the published study offline

Run `python app.py verify` from the repository root. It checks the release source lock, the original hashes of all 490 final-case files and the objective counts from all four approaches. Run `python app.py test` for 91 automated tests, including reconstruction of the archived model inputs and direct-baseline predictions after renaming. Neither command calls Gemini or changes devices.

Read `research/results.json`, `research/results.csv`, `evaluation/methods.md`, `evaluation/clarifications.md` and `docs/provenance.md` together. Exact-root accuracy uses all 50 diagnosable faults. API failures and abstentions are incorrect on those faults; correct abstention has its own ten-case denominator. Human support and recommendation metrics remain pending.

## Run the application

Use the recorded viewer with `python app.py replay`, or follow `docs/setup.md` for the full live GNS3 lab. The controller configuration, SSH trust, credentials and deployment identity are machine-specific and must be supplied locally. No VM image, populated PostgreSQL cluster or private project backup is committed. Dockerfiles describe fresh open-source image builds; repository changes can yield binaries different from the original tested images.

The included GNS3 template has wiring and image references only. The build/provision scripts create persistent node and monitor configurations. A new-machine deployment is not claimed identical to the tested original laptop unless separately verified.

## Distinguish reference and release hashes

The original pre-trial manifest is `research/reference-freeze.json`. Its historical paths describe the reference workspace. The organized source has a new release lock and a migration map because imports, paths, portable configuration and launchers changed. Raw final-case files remain byte-for-byte copies. Do not replace the original manifest with newly computed hashes and call that an unchanged pre-trial freeze.

## New experiments

Use a separately identified workspace, data directory, source lock, budget and control schedule. Run pilots before any new final acquisitions. The original final directories and model attempt ledger are research evidence, not scratch space. Do not rerun or overwrite them for a more favorable result. The harness and comparison sources are supplied for inspection and adaptation to a new protocol version.

Control labels and intervention acknowledgements must remain separate from diagnostic input. Keep the provider identifier, generation settings, evidence matrix, capture windows and timeout accounting fixed within a declared comparison. Hosted-provider behavior can change even for the same model name; new responses are new observations.

A new acquisition can require the study profile setup, which temporarily pauses guest scheduled maintenance. Restore its original timer state after measurements; do not leave an experimental pause in normal operation. The reference backups and prior receipts document the original protocol.

## Review and demonstration

Use the blinded pack and separate CSVs under `docs/review` for two distinct real reviewers. Preserve initial judgments and adjudication separately. The private blinding map is intentionally excluded from Git; obtain it from the study owner for analysis. No ratings are filled by AI.

Recorded-window processing and final API attempt durations are measured. Later UI viewing does not establish original incident-to-display latency. Live browser checks and isolated feedback tests are not human research review.
