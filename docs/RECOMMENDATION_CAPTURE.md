# Provider recommendation capture

Brain.fm response documents may contain a `similarTracks` list on a track object.
They may also contain track objects with an empty list, and a single response may
contain more than one list variant for the same track. An empty list therefore means
only that no recommendations were present in that particular object occurrence.

The current Brain.fm API can also return recommendations as a top-level `result`
list from `/v3/tracks/{track_id}/similar`. The response body does not repeat the seed
track. For HAR input, the extractor obtains the seed ID from the sanitized request
path and associates the returned tracks automatically. Request hosts, query strings,
tokens, and headers are not retained.

When a capture contains one or more explicit similar-track request paths, those
request-linked responses are the authoritative recommendation observations. Other
cached catalog responses in the same HAR may enrich the seed metadata, but their
embedded lists are not assigned to the visible capture context. Embedded
`similarTracks` fields remain the fallback for captures without explicit requests.

## Sanitized evidence model

`recommendation_graph.py extract` creates one content-addressed observation sidecar
per raw capture. It retains:

- source-capture filename, SHA-256 digest, format, size, and document count;
- optional user-recorded visible category, visible intent, seed ID, and capture time;
- safe provider track identifiers, titles, taxonomy values, and tags;
- every distinct ordered recommendation list and its occurrence count;
- directed seed-to-recommended edges, observed ranks, and document indices;
- empty-list observations and conflicting list variants.

It never retains media URLs, tokenized URLs, cookies, authorization fields, secrets,
or session credentials. Raw captures remain ignored by Git; sanitized observations
and the aggregate graph are trackable.

`recommendation_graph.py build` combines all sanitized sidecars without counting the
same content-addressed observation twice. An edge means only that the provider placed
a target in a seed track's captured `similarTracks` list. It does not establish actual
playback order, why the recommendation was made, personalization, or therapeutic
similarity.

## Collection procedure

Prefer semi-automated collection before automating browser interaction:

1. Open developer tools and enable **Preserve log** for Fetch/XHR responses.
2. Record the visible category, intent/activity, seed title, and local time separately.
3. Clear the network log, select the seed, wait for the similar-track interface, and
   exercise only the ordinary controls needed for the observation.
4. Export a HAR with response content or save the relevant JSON response.
5. Keep the raw capture under an ignored capture directory.
6. Run the sanitizer immediately and inspect its summary. A zero-edge observation is
   valid and should be retained.

Prefer a HAR when the response is a top-level recommendation list because it carries
the `/tracks/{track_id}/similar` request path needed to identify the seed. If only the
standalone JSON response is available, record the seed track ID explicitly:

```bash
.venv/bin/python recommendation_graph.py extract capture.json \
  --seed-track-id TRACK_ID --visible-category focus \
  --visible-intent light_work --context-method user_recorded
```

The ID after `/tracks/` is the canonical track ID. It is not the variation ID found
beside an MP3 filename under `variations`.

For a stability panel, collect approximately five seeds per major intent on three
different occasions. Use metadata-only observation for continuing catalog releases.
Acquire audio only when a track fills an underrepresented intent/taxonomy stratum or
represents a newly observed recommendation community.

Do not infer visible context from directory placement after the fact. Supply context
flags only when it was recorded during collection. Do not automate media downloads,
evade access controls, or preserve authenticated request material in tracked files.
