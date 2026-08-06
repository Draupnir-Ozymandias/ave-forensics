# N0 reconnaissance baseline

## Target

| Field | Value |
|---|---|
| Package | `com.lumenate.lumenateaa` |
| Version name | `7.0.0` |
| Version code | `380` |
| Minimum Android | API 24 |
| Target Android | API 35 |
| Architecture | Native Android, Kotlin/Java, Jetpack Compose |
| DEX count | 5 |
| Protection | R8; APKiD also reports emulator/debug checks |

## Specimen hashes (SHA-256)

| Component | SHA-256 |
|---|---|
| `base.apk` | `2ad4a6d313ca425023aba1864a51db87a0f2d38e697af2244fc42260d3136857` |
| `split_config.arm64_v8a.apk` | `8fb9a590d9b4f34c0099398796c0721ba5f6ebd325bf11b5cdfe32728373a5b7` |
| `split_config.xxhdpi.apk` | `e4eb3be1f2d6f32b76526a033748fa21f35b6036fbe95c81bffed7b443806d3d` |

The original files remain local-only and immutable.

## High-value static findings

Meaningful first-party classes survived obfuscation, including:

- `com.lumenate.lumenate.sessions.CppCommonSessionActivity`
- `com.lumenate.lumenate.services.LumenateSessionService`
- `com.lumenate.lumenate.strobe.StrobeManager`
- `com.lumenate.lumenate.model.HeadsetInfo`
- `com.lumenate.lumenate.common.Profile`

The ARM64 split contains `libstrobecontroller-lib.so` and `libspotifycyos-lib.so`. Exported JNI symbols include `doStrobe`, pause/resume/stop, synchronization, and headset connection callbacks. Readable native state includes current strobe frequency and on/off timing names. Together these are L1 artifact observations with a strong L2 hypothesis that the Java/Kotlin layer passes session arrays to a native timing engine.

## BLE findings

The observed connection requested MTU 256, negotiated MTU 498, and initially used a 7.5 ms connection interval (`interval=6`). Notifications were observed on:

- Battery Level: `00002a19-0000-1000-8000-00805f9b34fb`
- Custom: `2a84aaff-6738-4629-894c-346357b89a0c`
- Custom: `964fbffe-6940-4371-8d48-fe43b07ed00b`
- Custom: `12345678-9abc-4def-8012-3456789abcde`

Repeated GATT writes support, but do not prove, real-time or periodic control traffic. An HCI capture or instrumented write path is required to distinguish commands, buffered programs, synchronization, and status traffic.

Several `status=8` disconnections and rejected/unsupported connection updates were observed. No fatal application exception or native crash was found in the reviewed logs.

## Tooling result

JADX completed a broad pass with 162 method errors. A later pass exhausted Java heap during save at 99%. This does not invalidate successfully produced methods, but completeness must not be assumed. Future work should use a low-comment full pass plus targeted high-detail exports for first-party classes.

APKiD 3.1.0 identified R8 in all five DEX files and several anti-VM/debug checks. The ARM64 output currently contains only the APKiD header, so it should be recorded as “no reported finding” only after confirming the correct target and exit status.

## Leading hypotheses

1. Session parameter arrays enter a native strobe scheduler through `StrobeManager.doStrobe`.
2. The native layer maintains frequency and on/off values and emits callbacks toward headset control.
3. Nova uses a custom BLE characteristic for command/state traffic at low latency.
4. Timing may be streamed, periodically synchronized, or buffered; current evidence does not select one architecture.

## N0 gaps

- sanitized permission, SDK, endpoint, asset, and database inventories;
- Nova firmware and content-library versions;
- confirmed writable characteristic and packet-building code;
- raw-evidence secret/PII review and repository-history remediation;
- final acquisition manifest with tool versions and command exit statuses.

These gaps feed N0 closeout and N1; they do not require repeating the entire acquisition.
