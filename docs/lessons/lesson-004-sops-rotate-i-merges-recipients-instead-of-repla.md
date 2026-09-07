---
id: lesson-004-sops-rotate-i-merges-recipients-instead-of-repla
type: lesson
status: active
created: "2026-09-05"
owner: manu
tags: [garsync, lesson, sops, age, secrets]
---

# `sops --rotate -i` MERGES recipients instead of replacing them

- **Context:** SEC-001 secrets hardening — rotating from the master age key to a dedicated garsync identity
- **Finding:** `sops --rotate -i` re-encrypts the data key to the new recipient but KEEPS the old stanza working (both keys decrypt). The `_recipient` metadata line only reflects the first entry, hiding the merge. The correct tool after editing `.sops.yaml` is `sops updatekeys --yes` — it prints the exact `+++ / ---` recipient diff, which IS the verification evidence.
- **Pattern:** After changing `.sops.yaml` recipients, always use `updatekeys`, never `--rotate -i`. Verify by consequence: old key must fail (nonzero exit), new key must succeed.

**Tags:** `#sops` `#age` `#secrets`
