# Brain.fm corpus refresh — 2026-10-19

Completed ingestion, resumable audio analysis, and dashboard refresh. Original
recordings, HARs, screenshots and existing provider sidecars were preserved.

## Ingestion

- Added 55 validated exact-filename provider sidecars: 109 → 164 of 168 files.
- Existing 109 provider sidecars were retained without replacement.
- Added 22 sanitized recommendation captures: 16 → 38 observations.
- Rebuilt the graph: 1,274 nodes, 2,328 edges, 90 communities, and 93 seeds with
  sufficient repeated nonempty observations for drift assessment.
- Regenerated 168 recording manifests while preserving human curation.
- Retained duplicate audio as collection aliases, not additional unique inputs.

Session ingestion uses `ingest_brainfm_sessions.py`. It matches exact provider
variation filenames, prefers the latest date in a capture filename followed by
category-directory agreement, and refuses to replace existing sidecars. Source
catalog metadata can appear in a capture from another category; that is a
provider metadata match, not proof of playback or category membership.
Recommendation capture context is recorded from the collector's directory with
`context_method=capture_metadata`; it is separate from intrinsic provider tags.

## Batch and dashboard

| Result | Count |
| --- | ---: |
| Recording entries | 168 |
| Newly completed analyses | 22 |
| Prior completed analyses reused | 145 |
| Deferred | 1 |
| Failed or timed out | 0 |
| Unique byte-content inputs | 164 |
| Unique analyzed inputs | 163 |
| Indexed evidence objects | 32,458 |
| Dashboard evidence objects after byte-identity deduplication | 31,739 |
| Exploratory signal families | 3 |
| Intent assessments | 160 |

The new analyses cover seven Deep Work, five Travel, five Unwind, and five
Sleep and Wake entries. Afterthought is identical to its Guided Sleep copy;
therefore the 22 new paths add 21 unique byte-content inputs.

Rebuilt the corpus index, signal-family clustering, intent alignment,
recommendation communities/drift, provider context comparisons, longitudinal
snapshot, and self-contained dashboard. The new snapshot is
`ave_snapshot_bdc47c273366a3f8`, compared with `ave_snapshot_aea74231aabf5403`.
It records +21 / -0 unique inputs and 15 family-assignment changes. Family
assignment changes after refitting are not evidence that old audio changed.
Existing reused analyses retain configuration `1.3.0`; the 22 new runs record
configuration `1.4.0`. The dashboard exposes this mixed-version research corpus
rather than rewriting historical provenance.

Dashboard: [artifacts/dashboard/index.html](../artifacts/dashboard/index.html).
The three family model has silhouette score 0.2965; its labels remain
exploratory descriptions of measured signal features. Context association does
not establish efficacy or intended physiological effects.

## Retained exceptions

- **Multiverse:** 6,812.1 seconds, deferred by the existing 3,600-second limit.
- **Altered State:** local underscores differ from spaces in captured filename;
  no automatic rename or identity binding was performed.
- **Aura Cleansing:** abbreviated local filename does not identify the captured
  High/Medium/Low NEL variant; no variant was inferred.
- **Celestial Wanderings:** shortened filename remains an unbound provider
  alias, although byte identity with the longer local recording is established.
- **Between Dimensions:** latest captured `brightnessLevel=1.01` violates the
  current provider sidecar contract's 0–1 bound. Retained as an ingestion
  exception without clamping the value or blocking its audio analysis.
- Three older small Light Work HARs have no JSON response bodies. They were
  skipped; valid metadata for their recordings is available in other captures.
- Process and 45-minute Tranquility still lack exactly filename-matched
  screenshot files. No screenshot content was invented or rebound.

All 55 new sidecars validate against the provider JSON schema. All 164 current
sidecars pass the provider validator. Detailed generated ingestion exceptions
are in `artifacts/ingestion/`; batch status and provenance are in
`artifacts/batch/batch_summary.json`. New research runs record the working-tree
state honestly; they are not represented as clean-source release verification.

The ingestion tool has regression coverage for exact matching, preservation,
latest-capture selection and isolation of invalid metadata records.
