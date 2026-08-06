# Legal, privacy, and safety boundaries

## Authorization

Analyze only software, accounts, devices, communications, and licensed content lawfully controlled by the researcher. Do not test unrelated systems, enumerate other users, bypass authorization, or redistribute proprietary artifacts.

## Sensitive evidence

Never commit or publish:

- APKs, split APKs, firmware images, DEX/SO files, or full decompiler output;
- MobSF databases, secret keys, cache state, uploads, or downloads;
- raw Logcat, HCI, PCAP, filesystem, or network captures before review;
- email addresses, account IDs, device serials, Bluetooth addresses, tokens, cookies, or credentials;
- copyrighted commercial session audio or content definitions beyond lawful minimal excerpts.

Sanitized derivatives should use stable pseudonymous IDs and cryptographic source hashes.

## Device and exposure safety

Nova produces flashing light. Physical testing must minimize direct exposure, use a sensor fixture where possible, follow manufacturer warnings, and stop if anyone experiences discomfort. People with photosensitive epilepsy or related risk should not participate without appropriate medical oversight. This project does not certify product safety.

## Responsible protocol work

Controlled replay, if used, should target only the researcher's device, start with known-safe commands, use bounded intensity/duration, and include an immediate stop/disconnect path. Firmware modification is outside the initial roadmap.

## Claims

Engineering measurements may establish timing, intensity, synchronization, and protocol behavior. They do not establish neurological, psychological, therapeutic, or clinical outcomes.
