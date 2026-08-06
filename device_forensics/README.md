# Lumenate Nova Forensics

An independent, evidence-first workstream for reconstructing how the Lumenate Android application controls the Nova light mask.

This project owns APK analysis, Bluetooth Low Energy (BLE) traffic, device commands, native timing behavior, session reconstruction, firmware constraints, and physical validation. It does not become part of the AVE codebase. Integration occurs through versioned JSON exports that AVE validates and imports.

## Current position

Milestone N0 (APK reconnaissance) is substantially complete for app version `7.0.0` (`versionCode 380`). The investigation has established:

- a native Android Kotlin/Java application using Jetpack Compose;
- five DEX files compiled/obfuscated with R8;
- a native strobe engine in `libstrobecontroller-lib.so`;
- JNI entry points linking `StrobeManager` to frequency and on/off timing state;
- a low-latency Nova BLE connection and three custom notification characteristics;
- a strong next target: reconstruct the Java/JNI-to-BLE control path before deep native analysis.

See [PROJECT.md](PROJECT.md) for the operating model, [ROADMAP.md](ROADMAP.md) for milestones, and [reports/lumenate_nova/N0_RECONNAISSANCE.md](reports/lumenate_nova/N0_RECONNAISSANCE.md) for the evidence baseline.

## Repository map

```text
methodology/                   Scope, evidence levels, legal and safety rules
specimens/                     Local-only original APKs and acquisition metadata
static/                        Local-only generated static-analysis output
dynamic/                       Local-only raw logs and packet captures
protocol_reconstruction/      Reviewed protocol models and sanitized exports
physical_validation/          Measurement plans and reviewed optical results
contracts/                    Versioned Lumenate and AVE JSON contracts
reports/                       Sanitized milestone findings
tools/                         Reproducible acquisition/analysis utilities
```

Raw or proprietary evidence stays outside Git. Every publishable conclusion must point to a source hash, acquisition record, reviewed derivative, confidence level, and stated limitation.

## Immediate work

1. Close the remaining N0 inventory gaps and publish a sanitized baseline.
2. Trace `StrobeManager.doStrobe` arguments and `onStrobeValuesChanged` callbacks.
3. Identify the writable BLE characteristic and packet builder.
4. Capture controlled start, intensity, pause, resume, and stop events.
5. Publish the first contract-valid protocol export for AVE.

## AVE boundary

AVE owns signal analysis, evidence indexing, comparisons, clustering, scoring, and multimodal interpretation. This project exports device facts and reconstructions; AVE consumes them. Repositories should remain independently versioned and should use contract tests to detect schema drift.
