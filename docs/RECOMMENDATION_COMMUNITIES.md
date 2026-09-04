# Recommendation communities and capture drift

## Community discovery

Recommendation communities are discovered from the sanitized directed
`similarTracks` graph. Directed edges are projected to undirected unit weights and a
deterministic asynchronous weighted label-propagation algorithm is applied. Processing
order is fixed by descending weighted degree and provider track ID. Isolated nodes
remain explicitly unassigned.

The artifact reports modularity, community membership, internal and boundary edges,
and degree-ranked hubs. Provider taxonomy, visible session context, local filenames,
claimed intent, and AVE signal measurements do not participate in discovery.

After assignments are fixed, the following context is attached:

- provider mental-state and activity distributions;
- local stated-intent distributions;
- local AVE protocol-family distributions;
- Cramer's V and normalized mutual information for each post-hoc comparison.

Sparse tables—especially the local signal-family comparison—can inflate categorical
association statistics. Sample counts and the number of represented communities are
therefore retained beside every measurement.

## Repeated-capture drift

For each seed, recommendation lists within one sanitized capture are combined into a
non-empty target set. Drift is assessed only when the same seed has a non-empty target
set in at least two distinct content-addressed observations. Pairwise similarity uses
Jaccard overlap and reports retained, added, and removed target counts.

Empty versus populated track objects inside one response are recorded as structural
list variants, not temporal drift. Likewise, a seed recurring across captures with
fewer than two non-empty lists is marked `insufficient_nonempty_repeats`.

These analyses describe the captured recommendation graph. They do not reveal the
provider's internal algorithm, demonstrate personalization, establish playback order,
or imply therapeutic equivalence between tracks.
