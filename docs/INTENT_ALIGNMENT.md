# Claimed-intent versus observed-signature alignment

This layer asks a narrow, reproducible question: do recordings carrying the same
claimed library intent tend to occupy the same independently discovered signal
family?

It does not determine whether a recording produces its claimed mental, physical, or
therapeutic outcome. Answering that question would require controlled human-subject
data, outcome definitions, appropriate sampling, and an ethical study design.

## Separation of evidence and context

Protocol families are discovered without provider categories, stated intent,
filenames, transcripts, or outcome claims. Alignment is calculated only afterward.
This prevents the label being evaluated from helping construct the observed family.

## Reported measurements

- **Family consistency:** share of an intent cohort occupying its dominant family.
- **Corpus baseline:** prevalence of that family across all eligible recordings.
- **Association lift:** consistency divided by its corpus baseline. Lift is an
  unrestricted comparison ratio, not a probability.
- **Normalized excess consistency:** baseline-adjusted consistency from -1 to 1.
- **Recording alignment:** leave-one-out support among same-intent peers compared
  with leave-one-out corpus prevalence. Removing the recording prevents it from
  supporting its own assessment.
- **Cramer's V and normalized mutual information:** corpus-level association between
  intent labels and family assignments. Neither statistic establishes causation.

Intent cohorts smaller than three recordings are retained but not scored. Results
remain exploratory because the corpus is observational, provider-distributed, and
not balanced across intents. Duplicate audio inputs receive one canonical assessment
when their labels agree. A byte-identical input carrying conflicting intent labels is
excluded and reported explicitly instead of resolving the conflict by filename order.

Every output is bound to SHA-256 digests of both the Corpus Evidence Index and the
protocol-family artifact. A changed index or clustering result invalidates the prior
alignment artifact rather than silently mixing analytical states.
