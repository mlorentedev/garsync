---
id: lesson-025-a-payload-carried-offset-beats-a-configured-zone
type: lesson
status: active
created: "2026-09-25"
owner: manu
tags: [garsync, lesson, timezones, migrations, garmin, testing, gotcha]
---

# A payload-carried offset beats a configured zone

- **Context:** `specs/SUB-001` (the v1→v2 migration). `start_time` was stored from a naive local
  `startTimeLocal` while sleep came from a UTC epoch, so the plan was to normalise history to UTC with
  an explicit offset. Design §4.1 specified the rule: *use the stored offset if present, otherwise
  evaluate `GARSYNC_TZ` at the original date* — and the first draft of the spec set that fallback to
  `Europe/Madrid`.
- **Finding:** the data refused the default. Measured across all 100 activities in `data/garsync.db`,
  every payload carries `startTimeGMT`, it agrees with `beginTimestamp` in **100/100** rows, and the
  offsets **vary per row**: `-420` on 95 rows and `-480` on 5 (Garmin `timeZoneId` 153 and 121 — US
  Mountain/Pacific, not Madrid). A European default applied to a payload without a GMT value would
  have been **~8 hours wrong on the very history it was applied to**, and no fixture could have caught
  it, because the fixture would have encoded the same false assumption and agreed with itself.
- **Pattern:** when a source reports the same instant twice in two spellings, their **difference is
  the offset** — read it, do not infer it. Garmin sends `startTimeLocal` and `startTimeGMT` together,
  so the correct offset is a substring subtraction with no timezone database involved and no DST
  ambiguity to resolve: a fold-ambiguous local time is still paired with the right UTC value (the
  migration's DST-fold fixture passes for exactly that reason). Where a value genuinely cannot be
  read, **fail closed and name the rows** rather than substituting a configured guess, and let a
  configured zone be something an operator sets on purpose — never a default living in the code.
  Corollary: a configured zone's real job here was the *calendar-day boundary of a rollup*, which is a
  different question from "what instant was this", and mixing the two is how a timezone bug becomes
  invisible.
- **Second-order consequence, for the record:** normalising to UTC moved which calendar day a row
  belongs to, because `date(start_time)` now reads a UTC day. Two of the 100 activities changed day.
  Fixing the instant and choosing the day are two decisions; SUB-005 (#115) holds the second.

**Tags:** `#timezones` `#migrations` `#garmin` `#testing` `#gotcha`
