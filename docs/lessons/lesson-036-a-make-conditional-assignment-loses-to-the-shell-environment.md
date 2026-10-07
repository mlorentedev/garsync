---
id: lesson-036-a-make-conditional-assignment-loses-to-the-shell-environment
type: lesson
status: active
created: "2026-10-06"
owner: manu
tags: [makefile, sops, age, secrets, gotcha]
related: [lesson-004-sops-rotate-i-merges-recipients-instead-of-repla]
---

# Lesson 036 — `VAR ?= value` in a Makefile loses to the same variable exported by the shell

**Context:** The Makefile pinned garsync's dedicated age identity with
`export SOPS_AGE_KEY_FILE ?= /home/manu/.config/age/garsync.txt`. The dotfiles export
`SOPS_AGE_KEY_FILE` machine-wide, pointing at the master key.

**Problem:** `?=` assigns only when the variable is undefined, and a variable from the environment
is defined. `make sync` therefore ran with the master key, which cannot decrypt garsync's secrets
since the SEC-001 re-key (`sops -d` exit 128 with it, exit 0 with `garsync.txt`). The pin did nothing
on exactly the machines it was written for, and nobody noticed: sync was not being run while Garmin
was rate-limiting.

**Solution:** give the project's value its own name and assign the shared one unconditionally:

```make
GARSYNC_AGE_KEY ?= $(HOME)/.config/age/garsync.txt
export SOPS_AGE_KEY_FILE := $(GARSYNC_AGE_KEY)
```

A makefile assignment overrides the environment (unless `make -e`), and the project variable keeps
the override point: `make sync GARSYNC_AGE_KEY=…`. Check it with `make -pn help | grep
'^SOPS_AGE_KEY_FILE '` while the shell exports another value.

**Why:** `?=` reads as "default", but its real meaning is "unless anyone set it", and the shell is
someone. Any variable that a machine-wide setup also exports needs a project-specific name.
