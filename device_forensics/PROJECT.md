# Project charter

## Mission

Reconstruct, document, and physically validate the Lumenate Nova control protocol from lawfully acquired software, traffic, and device measurements while preserving provenance and separating observation from inference.

## Questions this project must answer

- How are sessions and segments represented?
- Where are pulse frequency, duty cycle, intensity, color, envelopes, and transitions calculated?
- Does the phone stream real-time changes or upload programs for local execution?
- Which BLE services and characteristics carry commands, state, battery, and synchronization data?
- What role does `libstrobecontroller-lib.so` play, and what remains firmware-controlled?
- How closely do declared parameters, BLE commands, and measured optical output agree?
- Which audio/light synchronization anchors can be exported reproducibly?

## Ownership boundary

| Lumenate Nova Forensics owns | AVE Forensics owns |
|---|---|
| APK, DEX, Smali, JNI, and native-library analysis | Audio/visual signal analysis |
| BLE services, characteristics, packets, and state | Cross-corpus indexing and search |
| Device and firmware constraints | Comparisons, clustering, and scoring |
| Session and command reconstruction | Multimodal interpretation |
| Physical optical validation | Import and downstream use of validated exports |

No codebase merge is planned. Integration is a versioned producer/consumer contract.

## Deliverables

- immutable local acquisition manifests and hashes;
- sanitized static and dynamic findings;
- a BLE service/characteristic map and command dictionary;
- session/segment timelines with light parameters;
- command streams with synchronization anchors;
- confidence and limitation statements for every reconstruction;
- physical-validation comparisons;
- contract-valid AVE-compatible evidence exports.

## Working principles

1. Preserve original specimens; never patch the N0 baseline.
2. Prefer two independent observations for protocol claims.
3. Trace Java/Kotlin semantics into JNI before interpreting stripped native code.
4. Treat decompiler output as an aid, not authoritative source.
5. Never publish credentials, identifiers, proprietary specimens, raw commercial content, or reusable tokens.
6. Use controlled experiments that vary one input at a time.
7. Record negative results and uncertainty.
8. Do not claim physiological or clinical efficacy from engineering evidence.

## Definition of done

The first major project objective is complete when at least one Nova session can be reconstructed from source artifact through BLE command stream to measured optical output, with timing error reported, all source hashes preserved, and the result exported under the pinned AVE evidence contract.
