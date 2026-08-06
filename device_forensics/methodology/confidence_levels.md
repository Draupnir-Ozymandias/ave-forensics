# Confidence levels

Confidence is an evidence-chain label, not a claim of product efficacy.

| Level | Name | Required support |
|---|---|---|
| L1 | Artifact observation | Identifier, value, string, symbol, or structure exists in a preserved artifact. |
| L2 | Functional association | Control/data flow connects the artifact to session, timing, BLE, or output behavior. |
| L3 | Runtime confirmation | The associated code path executes during a controlled action. |
| L4 | Transport confirmation | The value or derived representation appears in a captured BLE exchange. |
| L5 | Physical confirmation | Measured optical output agrees with the reconstructed parameter within stated uncertainty. |

Every finding must include:

- one level from L1–L5;
- a numeric confidence score from 0 to 1;
- the scoring method or rationale;
- source artifact/capture identifiers;
- alternative explanations;
- known limitations.

Levels are cumulative only when the chain is actually linked. An L5 optical measurement without a proven link to a specific packet does not automatically validate that packet interpretation.

Example:

- `10.0` near a pulse function: L1.
- `frequencyHz=10.0` passed into `doStrobe`: L2.
- the callback emits during a controlled 10 Hz segment: L3.
- the mapped field is present in BLE writes: L4.
- a photodiode measures 10 Hz within uncertainty: L5.
