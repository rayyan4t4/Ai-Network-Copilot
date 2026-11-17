# Technical report — research reference

This report records the completed original controlled study. The organized release and subsequent live UI checks are described separately in README.md and provenance.md. Independent human review and incident-to-display timing remain pending. Prepared with Codex and AI assistance.

## Abstract and findings

This project implements an out of band network investigation assistant in a four site GNS3 laboratory. SNMP counters, Syslog events, reachability probes and authorized read only snapshots feed a PostgreSQL evidence store. Deterministic rules combine related observations into incident hypotheses. A weighted evidence gate can withhold AI diagnosis when critical distinguishing observations are missing. Gemini explains sufficient observations and suggests fixed read only verification checks. Engineers retain authority over network changes.

The final protocol schedules 70 separate acquisition windows: 50 diagnosable faults, 10 healthy windows and 10 insufficient evidence instances. Four approaches process each immutable recorded window. At report generation, 280 approach outputs are recorded. Pilots, including an OSPF calibration correction, are excluded from final denominators.

The full system achieved 78.0% exact fault class and location accuracy over all 50 diagnosable faults. Correct abstention on insufficient evidence was 80.0% over 10 cases. Its detection F1 was 0.904. Provider and validation failures remain in the denominator. These results describe this controlled lab, not production networks.

The no gate variant recorded 41/50 correct fault roots and 6/10 correct insufficient evidence abstentions, compared with 39/50 and 8/10 for the full system. This run shows a tradeoff: the gate variant had more correct abstentions but lower fault accuracy. It does not demonstrate an accuracy gain from gating. Independent provider failures and accepted abstentions remain visible in the failure breakdown.

Automated checks validate response structure, cited identifier membership and fixed command identifiers. They do not establish that every prose claim is supported. Two independent human reviewers must complete the supplied blinded forms before unsupported claim rates or recommendation quality can be reported. Replay pipeline timings are available; injection to browser display latency is not established.

### Report contents

Problem and scope

Network implementation

Evidence pipeline and gate

Experimental method

Aggregate results

Per fault results and confusion tables

Review and limitations

Operations and demonstration

Conclusions and references

## Problem and scope

A single network fault can produce link, routing and downstream reachability alarms. Inspecting each independently obscures their common dependency. An LLM given an incomplete description may add an explanation that is more specific than the observations support. The implementation tests whether topology context and explicit evidence sufficiency improve diagnosis and abstention while keeping all proposed checks read only.

### Delivered capabilities

| Requirement | Implementation |
| --- | --- |
| Four site lab | HQ and three branches, 30 nodes and 33 links |
| Current observations | 17 SNMP and Syslog sources, 29 remote probe targets |
| Incident correlation | Device, interface, topology path and time based rules |
| Evidence sufficiency | Weighted required signals, critical checks, freshness and contradictions |
| AI investigation | Normalized evidence, curated references, tentative explanation and fixed checks |
| Engineer review | Confirm, reject or correct, ratings and persisted notes without learning |
| Controlled comparison | 70 final cases and four approaches with recorded requests and responses |

The implementation uses lightweight Linux containers, FRRouting, Open vSwitch and nftables. It reproduces routing, VLAN connectivity, LACP and observable policy behavior. It does not claim Cisco IOS command fidelity, Rapid PVST behavior, sticky MAC semantics or independent physical router resources. These substitutions were chosen for the existing laptop and VM constraints.

### Authority boundary

The trusted collector and experiment harness use fixed lab commands. The diagnostic application has no device command execution or configuration endpoint. Model supplied strings are never passed to a shell or SQL query. Ground truth resides in separate control files and is not available to diagnostic adapters.

## Related work and positioning

### Network operations capability

Miao and colleagues introduced NetEval to assess network operations knowledge and inference through a multilingual question set [R1]. That work motivates explicit evaluation of domain capability rather than assuming a general model can troubleshoot reliably. This project evaluates current operational observations and exact fault locations in one controlled lab. Its 70 acquisition windows are a different task and cannot be compared numerically with NetEval scores.

### Failure detection from packet captures

Tulczyjew and colleagues proposed LLMcap, a self supervised approach for PCAP failure detection using masked language modelling [R2]. This prototype does not train a packet representation model or inspect packet captures as its diagnostic input. It combines SNMP, events, probes and read only snapshots, then tests whether the available observations support a class and location hypothesis.

### External knowledge and provenance

Lewis and colleagues studied retrieval augmented generation by combining a language model with retrieved nonparametric information [R3]. The live prototype uses a small curated guidance store, while the paired structured comparison supplies its fixed curated entries consistently. This is not a reproduction of the paper's trained neural retrieval architecture. Current telemetry remains distinct from general guidance, and cited identifiers alone do not prove factual support.

### Intelligent network management

Long and colleagues describe an LLM based architecture for intelligent 6G operations, optimization and network health assessment [R4]. This project has a narrower educational scope: an out of band assistant for a four site emulated network. It does not optimize a 6G network, autonomously change configurations or claim a new model training method.

The evaluated contribution is the integration and measurement of these concerns: observable network evidence, dependency based grouping, an explicit sufficiency decision and tentative read only interpretation. Claims about reducing unsupported prose remain open until two independent human reviewers complete the supplied assessment.

## Network implementation

The head office and branches B1, B2 and B3 each contain a router, a multilayer switch, two access switches and three hosts. A shared WAN switch links the routers. MON HQ attaches to the head office IT VLAN and hosts monitoring and PostgreSQL. OSPF provides routed reachability between sites. Each site separates ADMIN, STAFF and IT VLANs.

| Site | ADMIN subnet | STAFF subnet | IT subnet |
| --- | --- | --- | --- |
| HQ | 192.168.10.0/24 | 192.168.20.0/24 | 192.168.30.0/24 |
| B1 | 192.168.110.0/24 | 192.168.120.0/24 | 192.168.130.0/24 |
| B2 | 192.168.210.0/24 | 192.168.220.0/24 | 192.168.230.0/24 |
| B3 | 192.168.31.0/24 | 192.168.32.0/24 | 192.168.33.0/24 |

Each subnet gateway is .1 and the reserved host address is .101. Router to multilayer switch transit links use routed /30 networks. The common router WAN is 10.0.0.0/24. MON HQ is 192.168.30.10. These addresses are kept in local evidence and are excluded from model transmissions.

Open vSwitch runs its userspace netdev datapath. LACP joins the two primary uplinks to the first access switch. A single uplink serves the second access switch. The normal ADMIN to STAFF policy is a stateless deny within each site. The expected baseline includes eight blocked host pair directions, alongside 124 allowed directions. Expected policy blocks are not fault labels.

### Study capacity reference

All three branch WAN egress interfaces use the same 2 Mbps traffic control profile in every final condition. The collector labels these interfaces with a configured effective capacity. Sustained utilization is based on measured interface counter demand relative to that reference. Virtual counters may account traffic before queue drops, so values above 100 percent describe offered demand and must not be presented as delivered wire throughput.

## Evidence pipeline

| Stage | Evidence and responsibility |
| --- | --- |
| Collection | SNMP state and rates every 10 seconds, probes every 3 seconds, read only snapshots every 15 seconds |
| Storage | PostgreSQL inventory, telemetry, operational checkpoints and incident records |
| Normalization | Source identifiers, device and interface identity, observation time and freshness |
| Correlation | Topology dependencies, stable OSPF absence, exact ACL flow match, measured sustained rates and probe outcomes |
| Gate | Required evidence fraction, all critical signals, no contradiction |
| Interpretation | Gemini receives normalized summaries and curated guidance |
| Presentation | Local live dashboard and paired study viewer with review forms |

These are configured intervals. The shared laptop, SSH collection and export add overhead; stored observation timestamps are authoritative. Missing or failed reads remain missing evidence. Poll counters require valid intervals and handle reset, discontinuity, reindex and stale outcomes. A nominal virtual NIC speed alone is not an effective capacity calibration.

The bridge reads a bounded consistent database snapshot through a SELECT only role. Source records include original logs and configurations locally. Model input selects controlled fact summaries rather than forwarding arbitrary log or configuration text. Data is treated as evidence, not instructions. Requests reject addresses and use the already approved Google endpoint only.

Incident lifecycle resolution requires positive fresh observations, such as restored administrative state and dependent probe success. An absence of alerts is insufficient by itself. Historical evidence and model inputs remain attached to archived results, so later recovery does not rewrite the evidence on which a diagnosis was based.

## Evidence sufficiency

For a candidate class, the gate score is the sum of available required evidence weights divided by the sum of all required weights. Passing requires a score of at least 0.8, all class specific critical signals and no contradictory evidence. Missing or stale facts earn no signal weight. The score represents evidence availability and is not a probability that the diagnosis is correct.

| Class | Critical distinguishing observations |
| --- | --- |
| Interface shutdown | Observed linked interface down and identified link event |
| OSPF loss | Persistent missing required neighbor, routing event, physical link up and observed passivity change from the healthy reference |
| ACL fault | Failed monitor flow, exactly matching deny rule and increasing deny counter |
| High utilization | Three sustained measured intervals and configured effective capacity |
| Unreachability | Two failed probes and fresh upstream status |

OSPF localization compares current passivity with a verified healthy configuration. The parser supports FRR interface level passivity rendering. The pilot showed that neighbor expiration could outlast the original capture window; the final OSPF capture offset is 90 seconds. Two appropriately separated missing neighbor snapshots are required. Normal broadcast WAN 2 Way neighbors are not classified as failed point to point adjacencies.

The full system withholds the model when its primary candidate lacks sufficient evidence. The no gate comparison uses exactly the same structured model input and output validation but omits that precondition. The output schema permits all fault classes and all observed devices. It never forces the expected class or target. Valid identifier membership alone cannot establish that the model explanation is supported.

The earlier Week 2 explanation adapter is retained for legacy records. Week 3 live integration uses the same frozen packet builder, unrestricted classifier and gate as the study, checks for a fresh matching evidence window, and displays the returned class and target separately from the rule hypothesis. The benchmark still measures recorded window replay rather than ordinary live queuing, and its extra healthy window audit is distinct from live incident triggered calls.

## Experimental method

The protocol and SHA256 file manifest were frozen before final collection. The schedule uses seed 20261117 and balances ten instances per category across branches. Each injection has a fixed acquisition window, a separately stored intervention acknowledgement and a checked restoration. Data acquisition never waits for the diagnostic algorithm to produce the desired answer.

| Condition | Intervention | Final cases |
| --- | --- | --- |
| Shutdown | Branch router eth0 administratively down | 10 |
| OSPF loss | Branch router eth0 passive while link stays up | 10 |
| ACL fault | Exact monitor to one host deny on branch MLS | 10 |
| Utilization | Sustained 3 or 4 Mbps UDP offered to a shaped branch WAN | 10 |
| Unreachability | One host suppresses ICMP replies | 10 |
| Healthy | Healthy network at the same acquisition profile | 10 |
| Insufficient | Two new faults per class with a critical source withheld from a copy | 10 |

The insufficient condition removes events for shutdown and OSPF, the earlier ACL counter snapshot, the capacity source reference, or upstream interface evidence for probe unreachability. Original observations are retained. Masked cases do not invent telemetry or reuse a sufficient final case as an additional independent trial.

B1 uses direct uncorrelated administrative link, OSPF event, utilization and probe alerts. A current positive neighbor snapshot clears a recovered OSPF alert. B2 supplies a short rule generated incident description. Both structured variants receive the same normalized observations, hypotheses and references. Approach evaluation order is seeded within cases. Gemini temperature is zero, output is bounded to 1400 tokens and requests are spaced at least 15 seconds apart. One retry is permitted for HTTP 429 or 503, with retained attempt histories. The declared study request cap is 300, including pilots. Provider weights are not claimed immutable.

The original resource guard was 260 attempts. A recorded resource only amendment extended it to 300 to complete the prespecified comparisons after retained service error retries increased request use. Diagnostic code, prompts, model settings, capture windows and scoring were preserved. Completed outputs, including failures, were not rerun. The original profile and freeze manifest are retained alongside the amendment.

## Aggregate results

Results below use all planned denominators only when all 280 outputs are recorded. Fault root accuracy includes abstentions, validation rejections and provider errors as incorrect. Correct abstention requires a valid inconclusive result on an insufficient case. API errors cannot earn abstention credit.

| Approach | Detect F1 | Exact root of 50 | Abstain of 10 | Errors |
| --- | --- | --- | --- | --- |
| Direct alerts | 1.000 | 33/50 | 0/10 | 0 |
| Short description AI | 0.039 | 1/50 | 9/10 | 1 |
| Structured AI without gate | 0.916 | 41/50 | 6/10 | 8 |
| Full system | 0.904 | 39/50 | 8/10 | 11 |

| Approach | Precision | Recall | Root accuracy 95 percent interval |
| --- | --- | --- | --- |
| Direct alerts | 100.0% | 100.0% | 52.2% to 77.6% |
| Short description AI | 100.0% | 2.0% | 0.4% to 10.5% |
| Structured AI without gate | 86.0% | 98.0% | 69.2% to 90.2% |
| Full system | 87.0% | 94.0% | 64.8% to 87.2% |

Detection compares an incident alert decision against 50 fault and 10 healthy instances. For valid structured outputs this is the correlator incident flag; B2 uses its returned classification. Failed outputs are conservatively charged as false negatives on faults and false positives on healthy windows. These pipeline scores include provider and validation availability, rather than measuring only the raw correlator. Diagnosis accuracy separately requires the exact class and location. Confusion tables expose healthy windows assigned a fault class even when the correlator had no alert.

Wilson intervals describe uncertainty in the observed proportions. Repeated trials share one topology and one laptop, so these intervals are descriptive and do not establish independence across production environments. The comparison is paired on recorded cases, not a randomized multi network field study.

## Failure analysis and acquisition quality

| Approach | Wrong class | Wrong location | Valid abstention | Service or validation error |
| --- | --- | --- | --- | --- |
| Direct alerts | 10 | 7 | 0 | 0 |
| Short description AI | 0 | 0 | 49 | 0 |
| Structured AI without gate | 0 | 0 | 9 | 0 |
| Full system | 0 | 0 | 9 | 2 |

This descriptive breakdown explains misses among the 50 diagnosable faults. It does not change the frozen scoring. A valid abstention can be appropriate caution but still fails the exact root requirement on these diagnosable cases. Provider and output validation errors are separated from wrong accepted interpretations. No human semantic quality ratings are inferred from these categories.

The median observed valid counter interval was 10.01 seconds and the median snapshot separation was 20.16 seconds. Median capture lag behind the exported database snapshot was 3.02 seconds, with a maximum of 8.59 seconds. These values show actual collection overhead beyond configured intervals on the shared host.

2 insufficient evidence windows had no primary candidate in the recorded analysis. These cases remain in the results. A missing candidate does not prove that the underlying network was healthy. It exposes a limitation in candidate construction or observation availability. The healthy window model audit and gate outcomes must therefore be interpreted separately.

In 1 diagnosable high utilization window, the detector produced no primary candidate. The single threshold baseline can alert on one high interval while the structured detector requires the latest three valid intervals to remain at or above 80 percent. Bursty virtual counter demand can break that condition. For example, final sequence 28 recorded a latest egress interval of about 75 percent after intervals above 100 percent. That miss remains in the denominator; the threshold was not adjusted after seeing it.

The protocol does not retry a wrong accepted diagnosis, an abstention or a structurally rejected response to obtain a better score. One retry is allowed only for the prespecified service statuses. All individual attempt histories and validation reasons remain available for inspection.

## Fault accuracy and timing

| Fault class | Direct alerts | Short description AI | Structured AI without gate | Full system |
| --- | --- | --- | --- | --- |
| interface shutdown | 10/10 | 0/10 | 10/10 | 10/10 |
| ospf loss | 3/10 | 1/10 | 10/10 | 9/10 |
| acl fault | 0/10 | 0/10 | 10/10 | 10/10 |
| high utilization | 10/10 | 0/10 | 9/10 | 9/10 |
| unreachability | 10/10 | 0/10 | 2/10 | 1/10 |

| Approach | Pipeline median ms | Pipeline p95 ms | Final API attempt median ms |
| --- | --- | --- | --- |
| Direct alerts | 16 | 31 | Not measured |
| Short description AI | 17,016 | 49,365 | 2,812 |
| Structured AI without gate | 17,516 | 56,944 | 2,594 |
| Full system | 17,047 | 52,832 | 2,430 |

Pipeline timing begins when an approach starts processing a recorded observation window and ends when its result record is prepared for persistence. The final JSON write is excluded. It includes request spacing and any retry delays. Successful results are summarized separately from failures. The final API attempt duration for each result is summarized separately; individual retry durations remain in the attempt audit. These are replay measurements and do not represent live injection to diagnosis latency.

The viewer implements browser render acknowledgements, but origin approval rejected opening it in this session. No display acknowledgement was synthesized. End to end incident to browser display latency and visual UI acceptance therefore remain unverified. An engineer can complete this measurement by running an authorized local browser session and a separately recorded demonstration.

## Confusion table Direct alerts

| Actual | Down | OSPF | ACL | Load | Probe | Good | Abstain | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| interface shutdown | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ospf loss | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| acl fault | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 0 |
| high utilization | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 |
| unreachability | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 0 |
| healthy | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 0 |
| insufficient | 2 | 0 | 0 | 2 | 6 | 0 | 0 | 0 |

Rows are actual acquisition categories. Columns are returned class labels or error. A class match can still have the wrong device or interface; exact root accuracy therefore differs from this table. An inconclusive disposition is an abstention even if a tentative class field is present. Use results.csv to inspect disposition and location together.

## Confusion table Short description AI

| Actual | Down | OSPF | ACL | Load | Probe | Good | Abstain | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| interface shutdown | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0 |
| ospf loss | 0 | 1 | 0 | 0 | 0 | 0 | 9 | 0 |
| acl fault | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0 |
| high utilization | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0 |
| unreachability | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0 |
| healthy | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 0 |
| insufficient | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 1 |

Rows are actual acquisition categories. Columns are returned class labels or error. A class match can still have the wrong device or interface; exact root accuracy therefore differs from this table. An inconclusive disposition is an abstention even if a tentative class field is present. Use results.csv to inspect disposition and location together.

## Confusion table Structured AI without gate

| Actual | Down | OSPF | ACL | Load | Probe | Good | Abstain | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| interface shutdown | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ospf loss | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| acl fault | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 |
| high utilization | 0 | 0 | 0 | 9 | 0 | 0 | 1 | 0 |
| unreachability | 0 | 0 | 0 | 0 | 2 | 0 | 8 | 0 |
| healthy | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 8 |
| insufficient | 2 | 2 | 0 | 0 | 0 | 0 | 6 | 0 |

Rows are actual acquisition categories. Columns are returned class labels or error. A class match can still have the wrong device or interface; exact root accuracy therefore differs from this table. An inconclusive disposition is an abstention even if a tentative class field is present. Use results.csv to inspect disposition and location together.

## Confusion table Full system

| Actual | Down | OSPF | ACL | Load | Probe | Good | Abstain | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| interface shutdown | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ospf loss | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 1 |
| acl fault | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 |
| high utilization | 0 | 0 | 0 | 9 | 0 | 0 | 1 | 0 |
| unreachability | 0 | 0 | 0 | 0 | 1 | 0 | 8 | 1 |
| healthy | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 7 |
| insufficient | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 2 |

Rows are actual acquisition categories. Columns are returned class labels or error. A class match can still have the wrong device or interface; exact root accuracy therefore differs from this table. An inconclusive disposition is an abstention even if a tentative class field is present. Use results.csv to inspect disposition and location together.

## Human review and limitations

Two independent real team members must score the blinded review pack. Each output includes its observations and fixed checks. Reviewers count factual claims and unsupported claims, assess recommendation relevance, read only status and support, and rate usefulness and evidence support. Initial ratings must remain independent. Adjudicated outcomes should be stored separately after agreement analysis.

The supplied Reviewer 1 and Reviewer 2 CSV files contain blank rating fields. No agent has impersonated a reviewer or filled research ratings. Unsupported claim rates, recommendation quality scores and inter reviewer agreement are not reported. Feedback endpoint tests use an isolated disposable database and cannot be interpreted as human study data.

### Limits on interpretation

One emulated network and shared host resources limit external validity. Virtual counters and userspace switching are not physical appliance performance measurements.

Unreachability injections suppress ICMP. They establish a failed management probe, not a device power failure. ACL localization is limited to supported exact match nftables expressions.

B1 is a transparent direct alert baseline, not a commercial monitoring product. B2 receives a rule generated short description and therefore already has a candidate hypothesis.

The full and no gate variants share deterministic hypotheses, evidence and validation. Their difference estimates the effect of withholding model requests under this gate and dataset, not a universal LLM safety guarantee.

Provider service availability and output validation affect measured accuracy. Every retained failure matters. The non dated model identifier does not guarantee reproducible provider weights.

Browser display timing, new UI visual checks and two human reviewer outcomes remain incomplete. Institutional formatting, team signoff and submission are not claimed.

## Operations and demonstration

The existing GNS3 VM and local controller must be running before the local services start. Use tools/start_week3.ps1 from the project folder. The live network dashboard uses port 8765 and the study review viewer uses port 8766. A local Gemini key and the existing explicit normalized summary consent are required only for new external interpretations. Archived results remain available without new model calls.

### Suggested demonstration sequence

1. Show the four site topology and fresh health for all 30 nodes. Explain expected VLAN policy blocks.

2. Open a recorded shutdown case. Follow source identifiers, the six dependent failures and the root interface observation.

3. Compare the same recorded case across B1, B2, no gate and full results. Explain the exact root denominator.

4. Open an insufficient case and show the missing critical signal and full system abstention without a model request.

5. Show fixed read only checks and the confirm, reject or correct feedback form. Explain that feedback does not train the system.

6. Show the result tables and clearly identify reviewer scores and display latency as pending.

Keep private database and portable lab backups local because they contain lab credentials and raw observations. The source handover excludes the Gemini key. The backup inventory and SHA256 manifest identify exact files. The restore test compares every application table count against a task created temporary database and then removes that temporary database.

### Remaining team actions

Complete the two reviewer forms, allow a local browser check when convenient, rehearse the explanation in your own words, confirm university report requirements and approve the final academic content. Rotate the previously disclosed Gemini key. These actions do not require rebuilding the completed lab or repeating valid recorded trials unless the protocol is intentionally changed.

## Conclusions and project evidence

The project delivers a reproducible network monitoring and investigation prototype with explicit evidence boundaries. The controlled comparison records both correct outcomes and failures, rather than assuming that a structured model response is factually correct. The gate can withhold a confident interpretation when distinguishing observations are absent. Quantitative conclusions must remain restricted to the recorded final study and must be supplemented by the pending independent human assessments.

### Project evidence

Original scope: FYP Proposal.docx and AI Network Copilot One Month Plan.docx.

Frozen protocol: evaluation/methods.md, matrix.json, profile.json and lab/evidence/evaluation/freeze.json. The original request allowance and its resource amendment are retained separately.

Acquisition and approach outputs: lab/evidence/evaluation/final. Control schedule and intervention acknowledgements remain in .local/evaluation/control.

Machine readable results: lab/evidence/evaluation/results.json and results.csv. Human review materials: deliverables/review.

Earlier network and telemetry verification: lab/evidence/topology/verification.json and lab/evidence/week1/telemetry-verification.json. Final checks and backup proofs: lab/evidence/week4.

### Future work

A separate next version could distinguish an initial traffic alert from the stronger evidence needed for a sustained utilization diagnosis. This would make uncertain or bursty rate windows explicit candidates instead of allowing a missing candidate to resemble a healthy window. Such a change needs a separately labelled evaluation using retained observations; it must not overwrite the Version 1 outcomes.

The unreachability results also motivate a clearer distinction between an observed probe failure and an unproven physical cause. Further studies should vary topology, background traffic and fault combinations, then measure a real live browser path. Independent human support assessments are required before claiming that a higher location accuracy or a gate alone establishes trustworthy explanations.

## References

[R1] Y. Miao et al. An Empirical Study of NetOps Capability of Pre Trained Large Language Models. 2023. https://arxiv.org/abs/2309.05557

[R2] L. Tulczyjew et al. LLMcap Large Language Model for Unsupervised PCAP Failure Detection. 2024. https://arxiv.org/abs/2407.06085

[R3] P. Lewis et al. Retrieval Augmented Generation for Knowledge Intensive NLP Tasks. NeurIPS 2020. https://arxiv.org/abs/2005.11401

[R4] S. Long et al. 6G comprehensive intelligence network operations and optimization based on Large Language Models. IEEE Network 2024. https://arxiv.org/abs/2404.18373

GNS3. Docker support in GNS3. https://docs.gns3.com/docs/emulators/docker-support-in-gns3

FRRouting. FRR User Manual release 8.4, OSPFv2 and passive interfaces. https://docs.frrouting.org/_/downloads/en/stable-8.4/pdf/

Google AI for Developers. Gemini API errors. https://ai.google.dev/gemini-api/docs/api-errors

Open vSwitch. Userspace datapath documentation. https://docs.openvswitch.org/en/latest/intro/install/userspace/

IETF. RFC 2328, OSPF Version 2. https://www.rfc-editor.org/rfc/rfc2328

IETF. RFC 3411, An Architecture for Describing SNMP Management Frameworks. https://www.rfc-editor.org/rfc/rfc3411

IETF. RFC 5424, The Syslog Protocol. https://www.rfc-editor.org/rfc/rfc5424

Technical references explain component behavior. They are not sources for the locally measured accuracy figures. Project observations, frozen source and result files support those figures. The report is a technical draft for team verification, not an assertion of institutional acceptance.
