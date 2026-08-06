# Protocol reconstruction workspace

Only reviewed, sanitized artifacts belong here.

Planned durable outputs:

- `service-map.json` — BLE services, characteristics, properties, and evidence IDs;
- `command-dictionary.json` — packet forms, field interpretations, and alternatives;
- `state-machine.md` — connection and session-control state transitions;
- `sessions/*.json` — contract-valid reconstructed sessions;
- `fixtures/` — minimal synthetic or sanitized captures for tests.

Raw JADX output, HCI/PCAP data, Logcat, APKs, and device identifiers remain in ignored local evidence storage.
