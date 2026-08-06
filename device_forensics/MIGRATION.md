# Standalone repository migration

This directory currently lives inside the AVE checkout, but its intended end state is an independent `lumenate_nova_forensics` repository and Codex project.

## Current risk

The parent AVE repository already tracks raw files under:

- `dynamic/lumenate_nova/adb/`
- `dynamic/lumenate_nova/bluetooth/`

Adding `.gitignore` prevents new untracked captures from being added accidentally, but it does not remove files already present in Git history. Those captures require a privacy/secret review before deciding whether to retain sanitized versions, remove them from the index, or rewrite published history.

## Safe split sequence

1. Freeze AVE and Lumenate changes long enough to inventory tracked paths.
2. Scan tracked dynamic logs for credentials, tokens, email/account identifiers, device serials, Bluetooth addresses, and proprietary content.
3. Preserve originals in encrypted/local evidence storage and verify hashes.
4. Copy only the project files permitted by the charter into a new sibling checkout named `lumenate_nova_forensics`.
5. Initialize independent version control there and confirm its `.gitignore` with representative specimen/log/cache names.
6. Remove the old workstream from the AVE index in a dedicated AVE change; do not delete the local evidence store.
7. If sensitive material reached a shared remote, coordinate a history rewrite and credential/token rotation as a separate, explicitly reviewed operation.
8. Register the new checkout as its own Codex project and keep this task history with it.
9. Add AVE importer contract tests using the golden fixture under `contracts/examples/`.

Do not use a normal repository merge later. AVE consumes released JSON exports; it should not import Lumenate source, specimens, or generated reverse-engineering output.
