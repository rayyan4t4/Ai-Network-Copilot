# Verification receipts

These files record checks actually run on the organized release. They do not certify production suitability or independent human review.

- `network/verification.json`: 243 routing, VLAN, LACP, ACL, reachability, SNMP and Syslog checks.
- `telemetry/telemetry-verification.json`: 11 collector/data checks.
- `live/`: API observation samples and the browser acceptance record.
- `tests.json`: actual test-suite outcomes and counts.
- `release.json`: publication checks and offline research integrity.

The first release observation kept all 60 samples fresh with 24 distinct exports and maximum observation age 9.1 seconds, but two samples showed 29/30 healthy devices. Its strict overall result is retained as failed. This distinguishes export freshness from momentary network-health observations. Recovered memory-allocation errors were also observed during the constrained-host release workflow; availability is not guaranteed during overload or sleep.

Browser checks directly observed the live overview, topology, device filter, raw evidence selection and an explicitly labelled recorded insufficient-evidence replay. The study-viewer address on port 8766 remained denied by a saved browser permission. Its API and persistence are tested separately. No browser screenshot, display latency or human rating is invented for it.
