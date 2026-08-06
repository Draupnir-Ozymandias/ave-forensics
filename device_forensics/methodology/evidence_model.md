# Evidence model

## Evidence chain

```text
immutable source artifact
  → reviewed derivative
  → observation
  → functional association
  → runtime event
  → transport interpretation
  → physical measurement
  → reconstruction
  → AVE-compatible export
```

Each link may be present, absent, or contested. Reports must not silently bridge missing links.

## Source record

Each local artifact or capture should have:

- stable source ID;
- SHA-256 hash;
- acquisition time and method;
- app, Android, device, and firmware versions where applicable;
- operator and environment notes;
- sensitivity classification;
- parent/source relationship for derivatives.

Raw source records remain local. Git receives only sanitized manifests, hashes, methods, reviewed findings, and lawful excerpts necessary to support a conclusion.

## Reconstruction record

A reconstructed session includes:

- session and segment identifiers;
- relative timing;
- light intensity and optional color;
- pulse frequency and duty cycle or explicit on/off durations;
- related device-command IDs;
- audio/light synchronization anchors;
- confidence and limitations;
- source hashes and acquisition provenance.

## AVE publication contract

The project publishes a `lumenate-protocol-export` bundle. The bundle pins its own schema version and the accepted AVE evidence schema version, currently `1.0.0`. It may contain device-specific reconstruction records plus canonical AVE evidence objects. AVE imports the bundle; it does not depend on this repository's internal code or raw evidence layout.

Schema changes follow semantic versioning:

- patch: clarifications that do not change validation;
- minor: backward-compatible optional fields;
- major: incompatible structural or semantic changes.
