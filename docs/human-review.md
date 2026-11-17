# Human review analysis plan

No human ratings are generated or inferred by the software. The two sheets require two distinct real reviewers, working independently before any discussion. Team confirmation of that provenance is still required; a program cannot establish human identity or independence.

Run tools/analyze_human_reviews.py after receiving the completed CSVs. Blank or invalid sheets produce a pending status and no quality metrics. Keep the initial sheets unchanged and record any adjudication separately. Do not regenerate blank forms over completed sheets.

All structurally valid recorded outputs, including abstentions and direct alert labels, are assessable. Provider errors and rejected outputs remain in objective accuracy and availability results, but do not receive an invented prose-quality rating. Reviewers use the actual diagnostic input, with local source records available to verify derived observations. Information withheld from the input must not be used to credit an unsupported claim.

For each reviewer and approach, unsupported claim rate is total unsupported factual claims divided by total factual claims. Recommendation relevance, read-only status and support rates use total recommendations as their denominator. A zero denominator is missing or not applicable, never an automatic zero-error or perfect score. Usefulness and evidence-support ratings are summarized descriptively on the 1-to-5 scale.

Agreement uses paired review IDs. Confirm/reject/correct decisions use unweighted Cohen kappa. Ordinal usefulness and support ratings use linear weighted kappa across 1 through 5. Exact agreement is also reported. Kappa is undefined when the expected disagreement is zero; perfect constant ratings must not be presented as a meaningful chance-corrected coefficient.

Report each reviewer's rates separately. A low unsupported-claim rate from an abstaining or terse system must be read alongside response coverage, exact-root accuracy and usefulness. Quality statistics do not replace the objective fault and insufficient-evidence denominators. Do not claim semantic support, recommendation quality or agreement until the completed independent sheets and provenance are available.
