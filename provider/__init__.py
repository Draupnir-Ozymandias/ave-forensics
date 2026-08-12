"""Provider-supplied metadata extraction and validation."""

from provider.brainfm import (
    extract_brainfm_sidecars,
    provider_sidecar_path_for,
    validate_provider_sidecar,
    write_provider_sidecars,
)

__all__ = [
    "extract_brainfm_sidecars",
    "provider_sidecar_path_for",
    "validate_provider_sidecar",
    "write_provider_sidecars",
]
