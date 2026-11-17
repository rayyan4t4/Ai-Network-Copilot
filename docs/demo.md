# AI Network Copilot demonstration and viva

Use the completed result files for exact figures. Do not memorize draft numbers or claim that automated citation checks establish factual support. Two reviewer assessments, browser visual checks and injection-to-display timing remain pending unless separately completed.

## Eight minute demonstration

1. **Network and scope, one minute.** Show HQ and three branches, VLAN separation, OSPF, LACP and the monitoring host. Explain that lightweight FRR/OVS/nftables containers reproduce the required observable behavior on this laptop. They do not emulate every Cisco feature.
2. **Evidence, one minute.** Open the live dashboard or a saved observation file. Show device identity, source record ID, observation time and freshness. Explain SNMP, Syslog, probes and authorized read-only snapshots.
3. **Correlated fault, two minutes.** Open one recorded final shutdown case. Trace the root router interface and dependent failures. Show the evidence gate, tentative explanation, supporting identifiers and fixed read-only checks.
4. **Missing evidence, one minute.** Open an insufficient-evidence case. Identify the missing critical source and show the full system's inconclusive result without a model call. The no-gate comparison uses the same available structured observations.
5. **Comparison, one minute.** Show results.csv, report tables or presentation charts. Explain the 50 fault, 10 healthy and 10 insufficient denominators. Point out errors and abstentions rather than hiding them.
6. **Feedback, one minute.** Show confirm, reject and correct decisions and ratings. Explain that feedback is saved without changing the model or rules. Any practice feedback must be clearly labelled demonstration data and excluded from human study scoring.
7. **Limitations, one minute.** Explain the single shared laptop, virtual counters, hosted model variability and outstanding human/browser checks.

## Likely viva questions

**What is your contribution?** A reproducible integration of current network evidence, topology correlation, explicit evidence sufficiency and read-only AI interpretation, evaluated through paired controlled cases. The contribution is not a newly trained foundation model.

**Why use AI if rules already produce a candidate?** Rules normalize and group observations. The model supplies a tentative explanation, limitations and verification checks. The comparison measures whether this assistance is useful and supported. Exact-root accuracy alone cannot establish explanation quality; human review is required.

**Is the gate score a confidence probability?** No. It is the fraction of available required signal weight. Passing also requires all critical signals and no contradictions. It has not been calibrated as a probability.

**Why not always ask the model?** Missing distinguishing observations can make a plausible explanation unsupported. The gate explicitly withholds the request, and the no-gate ablation tests the effect of that choice on the same recorded inputs.

**How is ground-truth leakage prevented?** Injection labels and acknowledgements are stored in a separate control directory. Diagnostic adapters receive only observations. Model input is an explicit whitelist of normalized summaries. The response schema permits every class and observed device rather than forcing the expected answer.

**Does B2 receive ground truth?** No. It receives a short description made from deterministic observed alert hypotheses. This already gives it a candidate, which must be disclosed when interpreting comparisons.

**Are all 70 instances different?** They are separate real acquisition windows, balanced across fault categories and branches. Ten insufficient cases involve separately injected faults with evidence withheld from copies. Repeated windows on one topology are not independent production environments.

**What exactly is a correct root diagnosis?** Correct class and device, plus interface where the protocol defines one. An abstention or API/validation error is incorrect for any of the 50 diagnosable faults.

**Why distinguish detection from diagnosis?** A system can detect dependent failures while identifying the wrong root. Structured-system detection uses the correlator incident flag; B2 uses its model classification. Exact root accuracy and confusion/location records are separate.

**How is an ACL distinguished from a generic unreachable host?** A failed monitor flow must exactly match a supported deny expression on its observed path, and the rule counter must increase between two snapshots. Unsupported expressions do not earn distinguishing evidence.

**How is OSPF loss localized?** The system checks missing required point-to-point neighbors over two snapshots, physical link state, an identified routing event and a passivity change from the healthy configuration. A normal broadcast 2-Way neighbor is not a failed required point-to-point adjacency.

**What did the pilots change?** FRR renders passivity at interface level, and neighbor expiry outlasted the initial capture offset. The parser was corrected and the OSPF window extended before the final freeze. Earlier attempts remain archived and excluded from final totals.

**How is high utilization defined?** Three valid measured intervals at or above 80 percent of a configured effective capacity reference. All branch WANs have the same 2 Mbps shaping reference throughout the experiment. Counter demand can exceed capacity because virtual counters may count traffic before drops.

**Does unreachability prove a device is off?** No. The injection suppresses ICMP replies. Observations establish a failed management probe, while power state and every physical cause remain unproven.

**Can the model execute its suggestions?** No. It returns fixed check identifiers. The application renders read-only command templates and has no device execution endpoint. The separately authorized harness performs controlled lab interventions.

**How do you handle hallucinations?** Structural checks reject malformed fields, unknown IDs, unknown devices and unapproved check IDs. The gate withholds insufficient requests. These controls do not prove prose support. Two real independent reviewers must assess unsupported claims.

**Does feedback train the system?** No. Confirm/reject/correct decisions, ratings and notes are persisted only. There is no online learning or automatic configuration change.

**What happens when Gemini fails?** Attempts, HTTP outcomes and validation failures remain recorded. The frozen protocol permits one retry for 429/503 and a fixed study request cap. Errors stay in accuracy denominators. Billing was not changed.

**What latency can you claim?** Recorded-window replay processing to prepared result, with request spacing and retries, and API attempt durations. The final file write and browser rendering are outside that timing. Incident injection to browser display is still unverified after browser access was rejected.

**Can this replace a production NOC?** No such claim is supported. The prototype is an educational out-of-band assistant. Production use needs stronger credentials, SNMPv3, deployment security, broader fault coverage, independent infrastructure tests and operational review.

**What remains before submission?** Two real reviewer sheets, authorized browser/UI checks and display timing, team verification of the work, required university formatting and approval. The team must be able to explain the code and results in its own words.

## Failure rehearsal

- If the provider is unavailable, show archived actual results and the retained error record. Do not invent a live answer.
- If the live bridge is disconnected, point out the stale-data warning and use the recorded case. Do not present an archived screen as current health.
- If the browser cannot be opened under current permissions, use Word, PowerPoint and local JSON/CSV evidence. State that the UI portion is pending.
- Never run the 70-case harness during an assessment unless the supervisor explicitly wants new injections. Recorded comparisons suffice for the ordinary demonstration.
