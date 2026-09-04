# Longitudinal corpus comparison

The longitudinal layer separates three kinds of change that should not be conflated:

1. **Corpus growth:** audio inputs are added or removed.
2. **Observed-family migration:** a retained input changes evidence-derived family
   after the corpus, feature space, or analysis methodology changes.
3. **Context drift:** the same input gains or loses library categories, stated
   intents, aliases, or provider taxonomy contexts.

## Durable snapshots

`corpus_history.py` binds a compact snapshot to the SHA-256 digests of the Corpus
Evidence Index, protocol-family artifact, and intent-alignment artifact. Snapshots
are content-addressed and stored in the tracked `history/corpus_snapshots/` directory.
Generated comparisons are written to `artifacts/longitudinal/`.

Running the command repeatedly against unchanged inputs does not create a second
snapshot. Once the corpus changes, the new state is compared with the latest distinct
snapshot. Family continuity uses Jaccard overlap of member input hashes and reports
each current family as stable, shifted, reconfigured, or new.

## Cross-context reuse and recommendations

Byte-identical audio appearing under multiple labels is preserved as cross-context
reuse. It is not automatically classified as a filing error. For example, a provider
may reuse one signal under deep-sleep and wind-down delivery contexts.

Recommendation behavior is a separate context layer. A “Similar Tracks” queue can
cross visible categories such as deep sleep, power nap, and guided sleep without
proving that the underlying audio or provider taxonomy changed. Future recommendation
captures should record the seed track, visible session context, recommended track,
rank or sequence position, capture time, and provider identifiers. Directory placement
alone must not be used to reconstruct those facts retroactively.

The current snapshot therefore records only evidence present in manifests and
validated provider sidecars. It preserves enough identity and context history for
later recommendation-edge ingestion without treating an observation as structured
evidence before it has been captured.
