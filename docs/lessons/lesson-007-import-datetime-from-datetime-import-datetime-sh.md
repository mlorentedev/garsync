---
id: lesson-007-import-datetime-from-datetime-import-datetime-sh
type: lesson
status: active
created: "2026-09-05"
owner: manu
tags: [garsync, lesson, python, datetime, typing]
---

# `import datetime` + `from datetime import datetime` shadowing breaks PEP 604 unions at import time

- **Context:** SEC-001 date typing in `routes/stats.py`
- **Finding:** `import datetime` followed by `from datetime import datetime` rebinds the name to the CLASS, so `datetime.date | None` resolves to `datetime.datetime.date` (a method_descriptor) and fails collection with `TypeError: unsupported operand type(s) for |`.
- **Pattern:** When both the `date` and `datetime` classes are needed, `from datetime import date, datetime` and use bare `date | None`. If the module itself is also needed, alias it (`import datetime as dt`) instead of importing it under the same name as the class.

**Tags:** `#python` `#datetime` `#typing`
