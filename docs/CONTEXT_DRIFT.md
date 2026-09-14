# Provider Context Drift

The context-drift layer compares labels that were created by different processes
without treating any one of them as ground truth. It keeps these dimensions
separate:

- the corpus directory's claimed intent;
- activity words encoded in the recording filename;
- provider primary activity and provider activity tags;
- the visible session intent recorded with a recommendation capture;
- the activity distribution of recommended tracks; and
- the independently discovered AVE protocol family.

Run it after rebuilding the corpus index, protocol families, and recommendation
graph:

```bash
.venv/bin/python context_drift.py
.venv/bin/python dashboard.py
```

The JSON artifact preserves every layer and every pairwise comparison. `consistent`
means all comparable pairs have at least one exact normalized label in common;
`divergent` means none do; `mixed` means some do; and `insufficient_context` means
fewer than two populated layers are available. Normalization changes case and
separators only. It does not silently equate semantically adjacent labels such as
`Learning` and `Study & Read`.

Recommendation transition counts describe captured provider relationships, not
observed playback order. Protocol families remain evidence-only and are displayed
beside context results rather than incorporated into the agreement status.

The layer does not measure therapeutic efficacy, catalog correctness,
personalization, recommendation causality, or physiological outcome. Provider
sidecar schema 1.1 preserves Brain.fm's mobile and web activities independently;
`taxonomy.activity` remains a compatibility alias for the mobile activity. Legacy
1.0 sidecars contain only that alias. Missing web activity is reported as missing
evidence, not inferred.
