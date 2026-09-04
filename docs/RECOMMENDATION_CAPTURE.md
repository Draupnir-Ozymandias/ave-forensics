# Provider recommendation capture

Brain.fm response documents may contain a `similarTracks` list on a track object.
They may also contain track objects with an empty list, and a single response may
contain more than one list variant for the same track. An empty list therefore means
only that no recommendations were present in that particular object occurrence.

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

For a stability panel, collect approximately five seeds per major intent on three
different occasions. Use metadata-only observation for continuing catalog releases.
Acquire audio only when a track fills an underrepresented intent/taxonomy stratum or
represents a newly observed recommendation community.

Do not infer visible context from directory placement after the fact. Supply context
flags only when it was recorded during collection. Do not automate media downloads,
evade access controls, or preserve authenticated request material in tracked files.
