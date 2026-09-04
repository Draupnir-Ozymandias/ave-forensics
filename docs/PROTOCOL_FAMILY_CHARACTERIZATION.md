# Protocol-family characterization

Protocol families are unsupervised groupings of measured signal behavior. They are
not provider categories, therapeutic mechanisms, or efficacy findings.

Each clustering run assigns three complementary forms of interpretation:

- **Semantic label:** a deterministic name derived from the dominant carrier-pair
  type and shared-modulation persistence within the family.
- **Defining signatures:** the strongest measured contrasts between the family and
  the complete clustered corpus. Numeric contrasts use family and corpus medians
  scaled by the corpus interquartile range. Categorical contrasts compare prevalence.
- **Representative recordings:** up to three members nearest the family centroid in
  the same normalized feature space used for clustering.

Provider taxonomy, stated intent, filenames, transcripts, and claims remain excluded
from both clustering and characterization. Their distributions are retained only as
post-hoc context. This separation is required before claimed-intent versus
observed-signature scoring: a provider label must never help define the signal family
against which that label is later evaluated.

Family identifiers and labels are reproducible for a fixed corpus index, feature
specification, and method version. They may change when the corpus grows or the
analysis configuration changes. Downstream work must therefore retain the source
index digest and clustering method version already stored in the family artifact.
