---
id: lesson-003-astro-component-error-handling
type: lesson
status: active
created: "2026-05-29"
owner: manu
tags: [garsync, lesson, astro, error-handling]
---

# Astro component error handling

- **Context:** Sprint 3 code review
- **Finding:** Bare `catch {}` blocks in Astro `<script>` tags swallow errors silently. Variable name collisions between `catch (err)` and DOM variables named `err` cause build failures in Astro/Vite.
- **Pattern:** Always use `catch (error) { console.error("[Component]", error); }` and name DOM error elements `errDiv` to avoid collisions with the catch variable.

**Tags:** `#astro` `#error-handling`
