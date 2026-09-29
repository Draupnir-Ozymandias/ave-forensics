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

Evidence-type, metric, unit, modality, channel/region, and time scope must be
compatible. A whole-file observation does not silently satisfy a stage-scoped
claim. Missing light/video analysis remains visible rather than being inferred
from a Generator plan.

Agreement is limited to rendered engineering fields. It does not establish
neurological entrainment, efficacy, therapeutic benefit, physical-device
equivalence, calibrated exposure, or safety.
