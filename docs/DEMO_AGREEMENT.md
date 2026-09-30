# Demo Observation and Field-Level Agreement

AVE Forensics implements the consumer side of Platform contract
`ave-demo-declaration@0.1.0` as a mandatory two-phase workflow.

## Phase 1: blind observation

```bash
.venv/bin/python demo_verification.py observe \
  /path/to/demo/verification-request.json \
  --output-dir artifacts/demo-portfolio/<demo-id>/observation
```

The observer rejects requests whose detector input advertises expected values
or tolerances. It verifies the input hash, selects carriers without declared
target frequencies, runs applicable detectors, and persists both
`demo-observation.json` and `ave-evidence.json`. The observation records that no
declaration, target, or tolerance was loaded during detection.

## Phase 2: comparison

If one declaration spans separately authorized detector artifacts, combine the
already persisted observations before comparison:

```bash
.venv/bin/python demo_verification.py bundle \
  artifacts/demo-portfolio/<demo-id>/observation-a/demo-observation.json \
  artifacts/demo-portfolio/<demo-id>/observation-b/demo-observation.json \
  --output artifacts/demo-portfolio/<demo-id>/observation-bundle.json
```

Bundling does not rerun detection or load declaration values. It verifies the
current SHA-256 of every primary and supporting artifact, retains each component
observation and evidence identifier, and removes a `not_evaluated` metric only
when another persisted observation supplies that metric.

Only after Phase 1 has persisted output:

```bash
.venv/bin/python demo_verification.py compare \
  /path/to/demo/<demo-id>-declaration.json \
  artifacts/demo-portfolio/<demo-id>/observation/demo-observation.json \
  --schema /path/to/ave_platform/contracts/ave-demo-declaration-0.1.0.schema.json \
  --output artifacts/demo-portfolio/<demo-id>/agreement-report.json
```

The comparison verifies declaration identity and schema validity, applies
field-level tolerances, retains calculated errors, and emits one of `agree`,
`disagree`, `unsupported`, `not_evaluated`, or `invalid_declaration` for every
claim. The demo label follows Platform rules exactly: `verified`,
`partially_verified`, or `exploratory`.

Every newly generated report is validated before it is returned against the
vendored Platform contract
`verification/contracts/ave-demo-agreement-report-0.1.0.schema.json`. Forensics
also verifies that contract's SHA-256 is exactly
`f4a2ce98dc407b0aa7f40dcfc636de98e6c8d498feda84ecec9e5b3a36292315`.
Contract drift or report drift raises an error instead of emitting a report.
The test suite validates tracked snapshots of all five canonical portfolio
reports against the same pinned contract.

Evidence-type, metric, unit, modality, channel/region, and time scope must be
compatible. A whole-file observation does not silently satisfy a stage-scoped
claim. Missing light/video analysis remains visible rather than being inferred
from a Generator plan.

Agreement is limited to rendered engineering fields. It does not establish
neurological entrainment, efficacy, therapeutic benefit, physical-device
equivalence, calibrated exposure, or safety.
