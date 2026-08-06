# Integration contracts

`lumenate-protocol-export.schema.json` is the producer contract for reconstructed Nova sessions. It pins `ave_evidence_schema_version` to `1.0.0`, matching the current AVE evidence contract.

Release policy:

1. Validate exports in this repository before publication.
2. Keep a golden, sanitized fixture for each supported contract version.
3. Validate the same fixture in AVE importer tests.
4. Reject unsupported major versions and unexpected AVE schema versions.
5. Change schemas deliberately under semantic versioning; never edit a released contract silently.

The bundled schema describes the boundary, not raw evidence storage. Commands may omit `payload_hex` when publishing the literal payload would be inappropriate; interpretations must still cite reviewed evidence IDs.
