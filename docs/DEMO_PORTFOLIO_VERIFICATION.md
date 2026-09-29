# Demo Portfolio Verification Status

Date: 2026-09-29

AVE Forensics implements the two-phase verification boundary defined by the AVE
Platform demo agreement:

1. `demo_verification.py observe` accepts a target-free verification request,
   analyzes the supplied artifact, and persists independent evidence.
2. `demo_verification.py compare` subsequently validates the Generator
   declaration against `ave-demo-declaration` 0.1.0 and performs field-level
   comparison against the persisted observation.

The observer rejects requests containing expected values or tolerances. Its
ordering attestation records that declarations, targets, and tolerances were not
loaded during detection. Comparison preserves `agree`, `disagree`,
`unsupported`, `not_evaluated`, and `invalid_declaration` as distinct states.

## Diagnostic portfolio result

| Demo | Evidence label | Agree | Disagree | Unsupported | Not evaluated | Invalid declaration |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `ave-demo-001-binaural-construction` | `verified` | 6 | 0 | 0 | 0 | 0 |
| `ave-demo-002-smooth-am-ramp` | `verified` | 7 | 0 | 0 | 0 | 0 |
| `ave-demo-003-gated-pulse-contrast` | `verified` | 8 | 0 | 0 | 0 | 0 |
| `ave-demo-004-four-region-light` | `exploratory` | 0 | 0 | 1 | 6 | 0 |
| `ave-demo-005-staged-av-comparison` | `partially_verified` | 2 | 0 | 4 | 7 | 0 |

All five declarations validate against the Platform schema. The schema SHA-256
is `aca39c90191762cde5048dfefc6f732d9e0c43e2da668194f2cc6cb04175ab45`.

These results are diagnostic because the current Forensics checkout contains
uncommitted implementation changes. Release promotion requires committing the
implementation and repeating observation and comparison from that clean source
state.

## Supported observations

- Demo 001 independently resolves duration, peak, separate left/right carrier
  frequencies, their difference, and channel routing.
- Demo 002 independently distinguishes smooth amplitude modulation from gated
  pulses, fits the modulation-rate curve, estimates modulation depth, and
  checks stereo identity.
- Demo 003 independently resolves pulse rate, duty cycle, explicit off-state,
  hard-gated pulse shape, and stereo identity. This classification is not
  treated as smooth amplitude modulation.

## Known gaps

- Demo 004 requires an independent rendered-video/light detector. The supplied
  target-free request currently identifies only silent audio, so Forensics does
  not infer region schedules from Generator plans or declarations.
- Demo 005 requires stage-aware temporal segmentation and AV clock comparison.
  Whole-file audio measurements cannot satisfy stage-scoped declarations.
- AVE Platform has not yet published a machine-readable agreement-report
  schema. The current report format follows the agreement document and preserves
  the required states and evidence-label rules.

## Reproduction

Persist evidence first:

```bash
.venv/bin/python demo_verification.py observe \
  /path/to/demo/verification-request.json \
  --output-dir artifacts/demo-portfolio/<demo-id>/observation
```

Only after that command succeeds, compare the declaration:

```bash
.venv/bin/python demo_verification.py compare \
  /path/to/demo/<demo-id>-declaration.json \
  artifacts/demo-portfolio/<demo-id>/observation/demo-observation.json \
  --schema /path/to/ave-demo-declaration-0.1.0.schema.json \
  --output artifacts/demo-portfolio/<demo-id>/agreement-report.json
```

Evidence labels describe engineering agreement only. They do not establish
neurological entrainment, therapeutic efficacy, exposure safety, or clinical
benefit.
