# Blind Rendered-Video Region Analysis

AVE Forensics can independently inspect short rendered-video detector inputs
without loading Generator recipes, resolved schedules, declaration targets, or
tolerances.

The detector:

1. verifies the request's MP4 SHA-256;
2. reads stream timing with `ffprobe`;
3. decodes a fixed-resolution RGB analysis stream with `ffmpeg`;
4. converts pixels to luminance and derives on/off timing signatures;
5. finds connected spatial components sharing each timing signature; and
6. persists stream measurements, region geometry, transitions, explicit off
   intervals, evidence IDs, configuration, source revision, and limitations.

It does not assume that the video contains four quadrants. Region count and
spatial position labels are derived from connected timing components. Region
schedules are independent only when their complete initial-state and transition
signatures differ.

Run the normal observation-first workflow:

```bash
.venv/bin/python demo_verification.py observe \
  /path/to/demo/verification-request.json \
  --output-dir artifacts/demo-portfolio/<demo-id>/observation
```

Only after the observation exists should the declaration be loaded by the
comparison command documented in `docs/DEMO_AGREEMENT.md`.

## Limits

- Encoded MP4 cadence is not physical display refresh.
- RGB code values are not calibrated luminance or optical measurements.
- Pixel reconstruction cannot establish the identity of the Generator recipe
  that produced the video.
- The analysis does not establish neurological entrainment, efficacy,
  therapeutic benefit, device equivalence, or exposure safety.
