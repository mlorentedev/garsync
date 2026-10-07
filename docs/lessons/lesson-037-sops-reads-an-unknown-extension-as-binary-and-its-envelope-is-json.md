---
id: lesson-037-sops-reads-an-unknown-extension-as-binary-and-its-envelope-is-json
type: lesson
status: active
created: "2026-10-06"
owner: manu
tags: [sops, secrets, docs, gotcha]
related: [lesson-036-a-make-conditional-assignment-loses-to-the-shell-environment]
---

# Lesson 037 — sops reads an unknown extension as binary, and the binary envelope is JSON

**Context:** The README and the docs site told a new user to edit secrets with
`sops secrets.env.enc`. The Makefile's own `sync` recipe always passed
`--input-type dotenv --output-type dotenv`, so the documented command and the one that ran had
diverged without anyone seeing it.

**Problem:** sops picks the store from the extension. `.enc` is not one it knows, so it falls back to
the **binary** store, and an encrypted binary file is a JSON envelope (`{"data": "ENC[…]", "sops":
{…}}`, checked by encrypting a dummy `plain.enc` with sops 3.13.1). Decrypting our dotenv-encrypted
file therefore parses it as that JSON envelope and fails with `Could not unmarshal input data: invalid
character 'G' looking for beginning of value`. That message reads like a wrong-key or corrupted-file
error, which is exactly what someone on a new machine is primed to suspect. (Measured with the sops
3.13.1 binary; the file's own metadata says it was written by `sops_version=3.11.0`.)

**Solution:** every command that touches the file names the format:
`sops --input-type dotenv --output-type dotenv secrets.env.enc`. The edit form was checked without
opening an editor or printing anything: with `EDITOR=true` it exits 200 (sops: file not modified,
the success path), the bare form exits 1, and the ciphertext stays byte-identical.

**Why:** a documented command that nobody runs is not verified by the gate. When the recipe in a
Makefile carries flags, the README's copy of the same command must carry them too. Run the
documented form, not the one you remember.
